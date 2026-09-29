"""creditiq CLI: case inspection, the configuration store (validate,
publish, version, diff) and the excluded-terms check. Processing, baseline
and scorecard commands land with their features in
docs/functional-requirements.md.
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


def _cmd_case_list(_args: argparse.Namespace) -> int:
    cases = store.list_cases()
    if not cases:
        print("no cases in the store yet")
        return 0
    for case in cases:
        print(f"{case['id']}\t{case['borrower']}\t{case['stage']}")
    return 0


def _cmd_case_show(args: argparse.Namespace) -> int:
    case = store.get_case(args.case_id)
    if case is None:
        print(f"no case {args.case_id!r}", file=sys.stderr)
        return 1
    print(json.dumps(case, indent=2))
    return 0


def _cmd_config_validate(_args: argparse.Namespace) -> int:
    sections = writer.load_authored_sections()
    print(f"OK — {len(sections)} section(s) validate: {', '.join(sorted(sections))}")
    return 0


def _cmd_config_publish(args: argparse.Namespace) -> int:
    record = writer.publish(data_root=Path(args.data_root), author=args.author, note=args.note or "")
    print(json.dumps(record, indent=2))
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
    sections = writer.load_authored_sections()
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
    case_sub.add_parser("list", help="list cases in the store").set_defaults(func=_cmd_case_list)
    case_show = case_sub.add_parser("show", help="print one case as JSON")
    case_show.add_argument("case_id")
    case_show.set_defaults(func=_cmd_case_show)

    config = sub.add_parser("config", help="the config store (policy, checklist taxonomy)")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("validate", help="validate every authored config/*.yaml section").set_defaults(
        func=_cmd_config_validate
    )
    config_publish = config_sub.add_parser("publish", help="publish an immutable config version")
    config_publish.add_argument("--author", required=True)
    config_publish.add_argument("--note")
    config_publish.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    config_publish.set_defaults(func=_cmd_config_publish)
    config_version = config_sub.add_parser("version", help="show the currently published version")
    config_version.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    config_version.set_defaults(func=_cmd_config_version)
    config_diff = config_sub.add_parser("diff", help="diff authored config against the published version")
    config_diff.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    config_diff.set_defaults(func=_cmd_config_diff)

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
