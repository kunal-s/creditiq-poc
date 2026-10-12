"""creditiq CLI: case inspection, the configuration store (validate,
publish, version, diff), RBL's reference record (template, import, show;
F-25.1) and the excluded-terms check. Scorecard commands land with F-26 in
docs/functional-requirements.md.

Publishing re-runs every case's checks afterwards (FRD principle 3), unless
--no-rerun is given.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import store
from .checks import excluded_terms
from .configstore import reader, writer

DEFAULT_DATA_ROOT = str(store.data_root())


def _cmd_case_list(args: argparse.Namespace) -> int:
    from . import cases, db

    conn = db.connect(Path(args.data_root))
    try:
        rows = cases.list_cases(conn)
    finally:
        conn.close()
    if not rows:
        print("no cases in the store yet")
        return 0
    for case in rows:
        print(f"{case.id}\t{case.borrower}\t{case.stage}")
    return 0


def _cmd_case_show(args: argparse.Namespace) -> int:
    from . import cases, db

    conn = db.connect(Path(args.data_root))
    try:
        case = cases.get_case(conn, args.case_id)
    finally:
        conn.close()
    if case is None:
        print(f"no case {args.case_id!r}", file=sys.stderr)
        return 1
    print(case.model_dump_json(indent=2))
    return 0


def _cmd_case_timings(args: argparse.Namespace) -> int:
    """F-02.4 / C9: stage timings of a case as CSV."""
    import csv

    from . import db

    conn = db.connect(Path(args.data_root))
    try:
        rows = conn.execute(
            "SELECT case_id, subject, stage, started_at, ms FROM stage_timings WHERE case_id = ? ORDER BY rowid",
            (args.case_id,),
        ).fetchall()
    finally:
        conn.close()
    writer_ = csv.writer(sys.stdout)
    writer_.writerow(["case_id", "subject", "stage", "started_at", "ms"])
    for row in rows:
        writer_.writerow(list(row))
    return 0


def _cmd_jobs_run(args: argparse.Namespace) -> int:
    """Run queued jobs until none is left (--once), or keep polling."""
    import time

    from . import jobs

    root = Path(args.data_root)
    while True:
        ran = jobs.run_pending(root)
        print(f"ran {ran} job(s)")
        if args.once:
            return 0
        time.sleep(args.poll)


def _cmd_jobs_list(args: argparse.Namespace) -> int:
    from . import db

    conn = db.connect(Path(args.data_root))
    try:
        for row in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (args.limit,)):
            print(f"{row['id']}\t{row['case_id']}\t{row['kind']}\t{row['status']}\t{row['attempts']}\t{row['error'] or ''}")
    finally:
        conn.close()
    return 0


def _private(args: argparse.Namespace) -> Path | None:
    return Path(args.private_config) if getattr(args, "private_config", None) else None


def _cmd_config_validate(args: argparse.Namespace) -> int:
    sections = writer.load_authored_sections(_private(args))
    print(f"OK — {len(sections)} section(s) validate: {', '.join(sorted(sections))}")
    return 0


def _cmd_config_publish(args: argparse.Namespace) -> int:
    """Publish, then re-run every case's checks (FRD principle 3), so that its findings, review
    items, queries, CAM and PD note follow the new version at once (--no-rerun: on their next run)."""
    root = Path(args.data_root)
    at_risk = writer.app_edits_at_risk(data_root=root, private_dir=_private(args))
    if at_risk and not args.discard_app_edits:
        print("The version now published was edited on the Administration screen, and the configuration files\n"
              f"say otherwise for: {', '.join(at_risk)}. Publishing the files would undo those edits.\n"
              "Carry the edits into the files first (`creditiq config diff` shows them), or publish with\n"
              "--discard-app-edits to replace them.", file=sys.stderr)
        return 1
    record = writer.publish(data_root=root, author=args.author, note=args.note or "", private_dir=_private(args))
    print(json.dumps(record, indent=2))
    if args.no_rerun:
        print("cases not re-run (--no-rerun): each follows the new version on its next run")
        return 0
    return _rerun_cases(root)


def _rerun_cases(root: Path) -> int:
    """Re-run the checks of every case in the store (as an upload or a decision does). A case that
    fails is reported and the others still run."""
    from . import db, pipeline

    if not db.db_path(root).is_file():
        print("re-ran the checks of 0 case(s): no case store yet")
        return 0
    conn = db.connect(root)
    try:
        ran, errors = pipeline.refresh_all_cases(conn, root)
    finally:
        conn.close()
    for case_id, error in errors.items():
        print(f"{case_id}: could not be re-run: {error}", file=sys.stderr)
    failed = list(errors)
    print(f"re-ran the checks of {len(ran)} case(s)")
    if failed:
        print(f"{len(failed)} case(s) not re-run: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def _cmd_config_version(args: argparse.Namespace) -> int:
    try:
        record = reader.published_version(Path(args.data_root))
    except reader.NoPublishedConfig as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    return 0


def _cmd_config_diff(args: argparse.Namespace) -> int:
    sections = writer.load_authored_sections(_private(args))
    dumps = {name: model.model_dump(mode="json") for name, model in sections.items()}
    authored_hashes = {name: writer.section_hash(dump) for name, dump in dumps.items()}
    try:
        published = reader.published_version(Path(args.data_root))
    except reader.NoPublishedConfig:
        print("no published version yet — every authored section is new:")
        for name in sorted(authored_hashes):
            print(f"  + {name}")
        return 0

    published_hashes = published["section_hashes"]
    changed = False
    for name in sorted(set(authored_hashes) | set(published_hashes)):
        a, p = authored_hashes.get(name), published_hashes.get(name)
        if a == p:
            continue
        changed = True
        if p is None:
            print(f"  + {name} (new)")
        elif a is None:
            print(f"  - {name} (removed)")
        else:
            print(f"  ~ {name} (changed)")
    if not changed:
        print("no changes since the published version")
    return 0


def _cmd_reference_template(args: argparse.Namespace) -> int:
    from . import reference

    Path(args.out).write_bytes(reference.template(Path(args.data_root)))
    print(f"wrote {args.out}")
    return 0


def _cmd_reference_import(args: argparse.Namespace) -> int:
    from . import db, reference

    conn = db.connect(Path(args.data_root))
    try:
        record, problems = reference.import_record(conn, Path(args.data_root), args.case_id, Path(args.file), args.author)
    finally:
        conn.close()
    for line in reference.problem_lines(problems):
        print(line, file=sys.stderr)
    if record is None:
        print("refused: nothing was stored", file=sys.stderr)
        return 1
    approval = 1 if record.approval else 0
    print(f"imported {record.workbook_name} for {record.case_id}: {len(record.deviations)} deviation row(s), "
          f"{approval} approval row(s); awaiting confirmation by an RBL reviewer")
    return 0


def _cmd_reference_show(args: argparse.Namespace) -> int:
    from . import db, reference

    conn = db.connect(Path(args.data_root))
    try:
        record = reference.load(conn, args.case_id)
    finally:
        conn.close()
    if record is None:
        print(f"no reference record for {args.case_id}")
        return 1
    print(record.model_dump_json(indent=2))
    return 0


def _cmd_check_excluded_terms(args: argparse.Namespace) -> int:
    return excluded_terms.main(
        [
            "--names",
            args.names,
            *(["--root", args.root] if args.root else []),
            *(["--check", *args.check] if args.check else []),
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="creditiq")
    sub = parser.add_subparsers(dest="command", required=True)

    case = sub.add_parser("case", help="inspect the case store")
    case_sub = case.add_subparsers(dest="case_command", required=True)
    case_list = case_sub.add_parser("list", help="list cases in the store")
    case_list.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    case_list.set_defaults(func=_cmd_case_list)
    case_show = case_sub.add_parser("show", help="print one case as JSON")
    case_show.add_argument("case_id")
    case_show.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    case_show.set_defaults(func=_cmd_case_show)
    case_timings = case_sub.add_parser("timings", help="export a case's stage timings as CSV (F-02.4)")
    case_timings.add_argument("case_id")
    case_timings.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    case_timings.set_defaults(func=_cmd_case_timings)

    job = sub.add_parser("jobs", help="the processing job queue (F-02.3)")
    job_sub = job.add_subparsers(dest="jobs_command", required=True)
    job_run = job_sub.add_parser("run", help="run queued processing jobs")
    job_run.add_argument("--once", action="store_true", help="run until the queue is empty, then exit")
    job_run.add_argument("--poll", type=float, default=2.0)
    job_run.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    job_run.set_defaults(func=_cmd_jobs_run)
    job_list = job_sub.add_parser("list", help="list recent jobs")
    job_list.add_argument("--limit", type=int, default=20)
    job_list.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    job_list.set_defaults(func=_cmd_jobs_list)

    config = sub.add_parser("config", help="the config store (policy, checklist taxonomy)")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    private_help = "a git-ignored directory whose <section>.yaml files replace config/'s (RBL's own norms and matrix)"
    config_validate = config_sub.add_parser("validate", help="validate every authored config/*.yaml section")
    config_validate.add_argument("--private-config", help=private_help)
    config_validate.set_defaults(func=_cmd_config_validate)
    config_publish = config_sub.add_parser(
        "publish", help="publish an immutable config version, then re-run every case's checks")
    config_publish.add_argument("--author", required=True)
    config_publish.add_argument("--note")
    config_publish.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    config_publish.add_argument("--private-config", help=private_help)
    config_publish.add_argument("--no-rerun", action="store_true",
                                help="publish only; each case follows the new version on its next run")
    config_publish.add_argument("--discard-app-edits", action="store_true",
                                help="publish the files even where they undo edits made on the Administration screen")
    config_publish.set_defaults(func=_cmd_config_publish)
    config_version = config_sub.add_parser("version", help="show the currently published version")
    config_version.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    config_version.set_defaults(func=_cmd_config_version)
    config_diff = config_sub.add_parser("diff", help="diff authored config against the published version")
    config_diff.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    config_diff.add_argument("--private-config", help=private_help)
    config_diff.set_defaults(func=_cmd_config_diff)

    ref = sub.add_parser("reference", help="RBL's reference record for a case (F-25.1)")
    ref_sub = ref.add_subparsers(dest="reference_command", required=True)
    ref_template = ref_sub.add_parser("template", help="write the baseline workbook to fill from RBL's record")
    ref_template.add_argument("--out", required=True)
    ref_template.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ref_template.set_defaults(func=_cmd_reference_template)
    ref_import = ref_sub.add_parser("import", help="validate and store a filled workbook (.xlsx) or its JSON form")
    ref_import.add_argument("case_id")
    ref_import.add_argument("file")
    ref_import.add_argument("--author", required=True, help="the user id of the person importing it")
    ref_import.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ref_import.set_defaults(func=_cmd_reference_import)
    ref_show = ref_sub.add_parser("show", help="print a case's reference record as JSON")
    ref_show.add_argument("case_id")
    ref_show.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ref_show.set_defaults(func=_cmd_reference_show)

    check = sub.add_parser("check", help="static checks")
    check_sub = check.add_subparsers(dest="check_command", required=True)
    excluded = check_sub.add_parser("excluded-terms", help="sweep for stakeholder names")
    excluded.add_argument("--names", required=True)
    excluded.add_argument("--root")
    excluded.add_argument("--check", nargs="+", metavar="NAME")
    excluded.set_defaults(func=_cmd_check_excluded_terms)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
