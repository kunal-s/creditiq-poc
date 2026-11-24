"""Page typing (FRD F-08.1, F-09; decision 14; Epic 3 of the classification restructure).

Each page, and each section of a page that a title opens, is typed on its own by the keyword lists
(config/ingestion/keywords.yaml), in this order:

1. Index pages. A page whose titles name `index_min_types` types or more is a cover or index, not each of them.
2. Categories. The categories whose types place a page among the first `categories.first_pages` pages, then the next
   ones if none does; every category that does is kept.
3. Keywords. Each section is placed within the chosen categories' types; one that does not place is tried against
   every type, and its type's category joins the chosen ones. Where look-alike types share a part (audited and
   provisional statements share the balance sheet), the run of sections they share decides, by each type's own words.
4. Continued. An untitled section at the head of a page continues the type the page before ended with (a table running
   onto the next page; the closing pages of a document).
5. Gap fill. An unplaced page between pages of one type, up to `max_gap` pages, takes that type.
6. The model, one page at a time, with the page's lines and the closed list; a title warning on the page for the type
   it names overrules it. Its answers are recorded and replayed like every model call.
7. What is left stays unplaced, with its three best guesses.

A page may carry several types: the end of the balance sheet and the start of the profit and loss on one page, each in
its own section. Documents are the runs of pages that carry one type."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from ..config.models import IngestionConfig
from ..llm.provider import ModelError, ModelRequest
from ..llm.recorder import ModelClient
from ..llm.schema_gen import classify_schema
from ..pageindex import Page
from . import keywords as K


@dataclass
class Section:
    page: int
    lines: list                      # the page's content lines in this section
    titled: bool                     # opened by a title of some part
    types: list[str] = field(default_factory=list)
    placed_by: str | None = None     # keywords | all_types | continued | gap | model | index
    score: float = 0.0
    candidates: list[tuple[str, float]] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
    note: str | None = None


@dataclass
class PageTyping:
    pages: dict[int, list[Section]]
    categories: list[str]
    trace: list[dict]
    cfg: IngestionConfig

    def types_of(self, no: int) -> list[str]:
        out: list[str] = []
        for s in self.pages.get(no, []):
            out += [t for t in s.types if t not in out]
        return out

    def page_info(self, no: int) -> dict:
        secs = self.pages.get(no, [])
        placed = [s for s in secs if s.types]
        cands = max(secs, key=lambda s: s.score).candidates if secs else []
        return {"types": self.types_of(no), "placed_by": placed[0].placed_by if placed else None,
                "type_candidates": [{"type": t, "score": s} for t, s in cands[:3]],
                "sections": [{"first_line": s.lines[0].idx if s.lines else 0, "types": s.types, "placed_by": s.placed_by,
                              "part": (s.signals or {}).get("part")} for s in secs] if len(secs) > 1 else []}


def _sub_page(kw, page: Page, lines: list) -> Page:
    """A section as a page of its own, its zones those its lines have on the whole page."""
    labels = {id(l): z for l, z in K.line_zones(kw, page)}
    sub = dataclasses.replace(page, words=[w for l in lines for w in l.words], lines=list(lines))
    sub._kw_lines = [(l, labels.get(id(l), "body")) for l in lines]  # type: ignore[attr-defined]
    return sub


def _titles_of(kw, text: str) -> set[str]:
    """The parts whose title phrases a title line holds."""
    z = K.Zones(text, "", "", confused=kw.settings.matching.confused_digits)
    return {pn for pn, p in kw.parts.items() if any(K._found(kw, e, z, "title") for e in p.title)}




def _sections(kw, page: Page) -> list[tuple[list, bool]]:
    """The page cut at each title line that opens a part below the page's first lines: (lines, opened by a title)."""
    labelled = K.line_zones(kw, page)
    heads = [i for i, (l, z) in enumerate(labelled) if z == "title" and _titles_of(kw, l.text)]
    # Title lines in a row are one heading; the page's own heading (before any body line) does not cut it.
    first_body = next((i for i, (_, z) in enumerate(labelled) if z == "body"), len(labelled))
    cuts = [i for i in heads if i > first_body and (i - 1) not in heads]
    if not cuts:
        return [([l for l, _ in labelled], bool(heads))]
    out, start = [], 0
    for c in cuts:
        if c > start:
            out.append(([l for l, _ in labelled[start:c]], start == 0 and any(h < first_body for h in heads)))
        start = c
    out.append(([l for l, _ in labelled[start:]], True))
    return out


def _scores(cfg: IngestionConfig, sub: Page) -> list[dict]:
    return K.score_types(cfg, [sub])


def _candidates(cfg: IngestionConfig, ranked: list[dict], allowed: set[str] | None) -> list[dict]:
    s = cfg.keywords.settings  # type: ignore[union-attr]
    pool = [r for r in ranked if r["eligible"] and (allowed is None or r["type"] in allowed)]
    if not pool:
        return []
    best = pool[0]["score"]
    return [r for r in pool if r["score"] >= s.page_threshold and r["score"] >= best - s.margin]


def type_pages(cfg: IngestionConfig, pages: list[Page], model: ModelClient | None) -> PageTyping:
    kw = cfg.keywords
    assert kw is not None
    s = kw.settings
    by_id = cfg.document_types.by_id()
    enabled = cfg.document_types.enabled_ids()
    real = [p for p in pages if not p.blank]
    trace: list[dict] = []

    # 1. Index and cover pages: titles of many parts, of more than one document type's family.
    out: dict[int, list[Section]] = {}
    index_pages = set()
    for p in real:
        parts = _titles_of(kw, K.zones(kw, p).title)
        owners = {frozenset(t for t, tt in kw.types.items() if pn in tt.parts and t in enabled) for pn in parts}
        if len(parts) >= s.index_min_types and len({min(o) for o in owners if o}) >= 2:
            index_pages.add(p.no)
            out[p.no] = [Section(p.no, p.content_lines(), True, [], "index", 0.0,
                                 note=f"titles {len(parts)} parts of several documents: a cover or index page")]

    # Every section scored against every enabled type once.
    secs: list[tuple[Section, Page, list[dict]]] = []
    for p in real:
        if p.no in index_pages:
            continue
        out[p.no] = []
        for lines, titled in _sections(kw, p):
            sub = _sub_page(kw, p, lines)
            sec = Section(p.no, lines, titled)
            ranked = _scores(cfg, sub)
            sec.candidates = [(r["type"], r["score"]) for r in ranked[:3]]
            sec.score = ranked[0]["score"] if ranked else 0.0
            out[p.no].append(sec)
            secs.append((sec, sub, ranked))

    # 2. Categories, from the first pages, then the next ones.
    cat_of = {t: by_id[t].category for t in by_id}
    chosen: list[str] = []
    first = [no for no in sorted(out) if no not in index_pages]
    for start in range(0, len(first), s.categories.first_pages):
        window = set(first[start:start + s.categories.first_pages])
        for sec, _, ranked in secs:
            if sec.page in window:
                for r in ranked:
                    if r["eligible"] and r["score"] >= s.categories.threshold and cat_of[r["type"]] not in chosen:
                        chosen.append(cat_of[r["type"]])
        if chosen:
            break
    trace.append({"step": "categories", "chosen": list(chosen)})

    # 3. Keywords: within the chosen categories, then against every type.
    for sec, _, ranked in secs:
        allowed = {t for t in enabled if cat_of[t] in chosen}
        cands = _candidates(cfg, ranked, allowed)
        how = "keywords"
        if not cands:
            cands = _candidates(cfg, ranked, None)
            how = "all_types"
            if cands and cat_of[cands[0]["type"]] not in chosen:
                chosen.append(cat_of[cands[0]["type"]])
        if cands:
            # Look-alikes that share the part stay candidates: the run they are in decides between them (a profit and
            # loss under a "provisional financial statements" heading is provisional), not this section alone.
            part = cands[0]["signals"].get("part")
            mates = [r["type"] for r in ranked if part and r["type"] not in [c["type"] for c in cands]
                     and part in kw.types[r["type"]].parts and not r["signals"]["contrary"]
                     and (how == "all_types" or r["type"] in allowed)]
            sec.types = [c["type"] for c in cands] + mates
            sec.placed_by = how
            sec.signals = cands[0]["signals"]
    # Look-alikes that share a part: the run of sections whose candidates overlap decides, by each type's own words.
    order = [sec for sec, _, _ in secs]
    subs = {id(sec): sub for sec, sub, _ in secs}
    i = 0
    while i < len(order):
        if len(order[i].types) <= 1:
            i += 1
            continue
        group = set(order[i].types)
        j = i
        while j + 1 < len(order) and set(order[j + 1].types) & group:
            j += 1
            group |= set(order[j].types)
        run = order[i:j + 1]
        ranked = [r for r in K.score_types(cfg, [subs[id(x)] for x in run]) if r["type"] in group and r["eligible"]]
        keep = [ranked[0]["type"]] if ranked else []
        for x in run:
            if len(x.types) > 1:
                x.types = [t for t in x.types if t in keep]
                if not x.types:
                    x.placed_by = None
        i = j + 1

    # A section of a type whose parts are all another's, next to a section of that other type, carries both: an
    # acknowledgement filed with its computation is the acknowledgement and part of the return.
    for k, sec in enumerate(order):
        for nb in (order[k - 1] if k else None, order[k + 1] if k + 1 < len(order) else None):
            if nb is None:
                continue
            for t in list(nb.types):
                if t not in sec.types and any(K.within(cfg, u, t) for u in sec.types):
                    sec.types.append(t)

    # 4. Continued: an untitled section at a page's head takes the type the page before ended with.
    prev_last: list[str] = []
    for no in sorted(out):
        page_secs = out[no]
        if page_secs and page_secs[0].placed_by != "index":
            head = page_secs[0]
            if not head.types and not head.titled and prev_last:
                head.types, head.placed_by = list(prev_last), "continued"
            prev_last = next((x.types for x in reversed(page_secs) if x.types), prev_last if not page_secs else [])
        else:
            prev_last = []

    # 5. Gap fill: unplaced pages between pages of one type.
    nos = sorted(out)
    for k, no in enumerate(nos):
        if any(x.types for x in out[no]) or out[no] and out[no][0].placed_by == "index":
            continue
        before = next((out[nos[m]] for m in range(k - 1, -1, -1)), None)
        for g in range(1, s.max_gap + 1):
            if k + g >= len(nos):
                break
            after = out[nos[k + g]]
            if any(x.types for x in after):
                left = next((x.types for x in reversed(before or []) if x.types), None)
                right = next((x.types for x in after if x.types), None)
                if left and left == right and all(not any(x.types for x in out[nos[m]]) for m in range(k, k + g)):
                    for m in range(k, k + g):
                        for x in out[nos[m]]:
                            x.types, x.placed_by = list(left), "gap"
                break

    # 6. The model, one page at a time.
    if model is not None:
        by_no = {p.no: p for p in real}
        for no in nos:
            if no in index_pages or any(x.types for x in out[no]):
                continue
            answer = _ask(cfg, by_no[no], model)
            trace.append({"step": "model", "page": no, **answer})
            t = answer.get("type")
            if t:
                why = _ruled_out(cfg, by_no[no], t)
                if why:
                    for x in out[no]:
                        x.note = f"the model named {t}, but the page carries {why}"
                    continue
                for x in out[no]:
                    x.types, x.placed_by = [t], "model"
                    x.note = answer.get("reason")
    return PageTyping(out, chosen, trace, cfg)


def _ruled_out(cfg: IngestionConfig, page: Page, doc_type: str) -> str | None:
    """The title warning on the page that rules `doc_type` out: its own, or one on every one of its parts."""
    kw = cfg.keywords
    assert kw is not None
    own = K.score_words(kw, kw.types[doc_type], K.zones(kw, page)).ruled_out if kw.types[doc_type].has_words() else None
    if own:
        return own
    ps = K.part_scores(kw, page)
    outs = [ps[pn].ruled_out for pn in kw.types[doc_type].parts]
    return outs[0] if outs and all(outs) else None


def _ask(cfg: IngestionConfig, page: Page, model: ModelClient) -> dict:
    offered = [d for d in cfg.document_types.documents if d.enabled]
    ids = [d.document_type for d in offered]
    types = "\n".join(f"- {d.document_type}: {d.display_name} ({d.category})" for d in offered)
    lines, budget = [], cfg.llm.classify_chars
    for l in page.content_lines():
        row = f"{l.id}: {l.text}"
        if budget - len(row) < 0:
            break
        budget -= len(row) + 1
        lines.append(row)
    pr = cfg.llm.prompts["classify_page"]
    req = ModelRequest("classify_page", pr.system.strip(),
                       pr.user.replace("{{types}}", types).replace("{{lines}}", "\n".join(lines)).strip(), classify_schema(ids))
    try:
        ans = model.call(req)
    except ModelError as e:
        return {"type": None, "reason": f"model unavailable ({e.code}): {e}", "model_error": e.code}
    t = ans.get("type")
    return {"type": t if t in ids else None, "reason": str(ans.get("reason", ""))[:300]}


def documents(typing: PageTyping, pages: list[Page]) -> tuple[list[tuple[str, list[Page]]], list[list[int]]]:
    """(type, pages) for each run of consecutive non-blank pages carrying one type, in page order; and the runs of
    pages left unplaced."""
    real = [p for p in pages if not p.blank]
    runs: list[tuple[str, list[Page]]] = []
    open_runs: dict[str, list[Page]] = {}
    unplaced: list[list[int]] = []
    for p in real:
        types = typing.types_of(p.no)
        for t in list(open_runs):
            if t not in types:
                runs.append((t, open_runs.pop(t)))
        for t in types:
            open_runs.setdefault(t, []).append(p)
        if not types:
            if unplaced and unplaced[-1][-1] == p.no - 1:
                unplaced[-1].append(p.no)
            else:
                unplaced.append([p.no])
    runs += list(open_runs.items())
    # A run of an inner type wholly inside a run of the type that holds it (an acknowledgement inside a return) is
    # carried on its pages, but read once, as part of that document.
    inner = [r for r in runs if any(K.within(cfg_of(typing), r[0], o[0]) and {p.no for p in r[1]} <= {p.no for p in o[1]}
                                    for o in runs)]
    runs = [r for r in runs if r not in inner]
    runs.sort(key=lambda r: (r[1][0].no, r[0]))
    return runs, unplaced


def cfg_of(typing: PageTyping) -> IngestionConfig:
    return typing.cfg

