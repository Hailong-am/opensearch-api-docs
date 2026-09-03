#!/usr/bin/env python3
"""
Generate the AOSS remove-overlay from the customer-facing DP API allowlist.

Source of truth: aoss-dp-api-allowlist.md (parser V2 doc/APIs.md, curated).
Strategy: ALLOWLIST. Every OSS base (path, method) NOT covered by the allowlist
is removed. Upstream additions are removed by default (drift-safe).

Scope: GA + undocumented (marked but customer-reachable). Exclude only the
force-denied / internal (marked with the lock emoji) rows.

Invariant (fail the build): every allowlist entry MUST match >=1 base
(path, method). Unmatched entries are reported -- they are either a parser-path
typo, an OSS-spec gap, or an AOSS-only path that needs an extension overlay
(NOT an allowlist entry). A silent miss would let a hand list drift.
"""
import sys, re, yaml, json, argparse
from pathlib import Path

LOCK = "\U0001F512"   # 🔒 exclude
WARN = "\u26A0"       # ⚠️ keep (undocumented)

HTTP_METHODS = ("get", "post", "put", "delete", "head", "patch")


def parse_allowlist(md_path):
    """
    Return list of (methods:set, parser_path:str, excluded:bool) from fenced
    code blocks. A row is excluded if the lock marker appears EITHER on the row
    itself OR in the enclosing '##' section heading (FineTune marks its whole
    section that way, not each line).
    """
    text = Path(md_path).read_text()
    entries = []
    in_block = False
    section_locked = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("##"):               # section heading (## or ###)
            # a new top-level '## ' section resets the lock; '### ' inherits.
            if s.startswith("## "):
                section_locked = LOCK in line
            elif LOCK in line:
                section_locked = True
            continue
        if s.startswith("```"):
            in_block = not in_block
            continue
        if not in_block or not s:
            continue
        excluded = (LOCK in line) or section_locked
        m = re.match(r"^([A-Z|]+)\s+(\S+)", s)
        if not m:
            continue
        methods = set(x.lower() for x in m.group(1).split("|"))
        if not methods <= set(HTTP_METHODS):
            continue
        path = m.group(2)
        entries.append((methods, path, excluded))
    return entries


def normalize(parser_path):
    """
    Normalize a parser path to a SET of candidate canonical forms (every path
    variable -> '*'). A set, not a string, because some parser rows are glued
    or notation-variant and can legitimately match more than one base path.

    Reconciliations (parser notation -> OpenAPI notation), grounded in the base:
      _mappings            -> _mapping        (base models only the singular)
      /_setting (singular) -> /_settings      (base models only the plural)
      _all as a snapshot id-> *               (/_snapshot/*/_all == /_snapshot/*/*)
      pipeline<any-thing>  -> pipeline AND pipeline/*  (glued variable, base splits)
      .../models/ (trailing slash, no var) -> .../models/*  (parser dropped the var)
      _search_ (flow typo) -> _search
    """
    p = parser_path.split("?", 1)[0]
    p = p.replace("aoss-automated", "*")
    # flow_framework source typo: trailing-underscore _search_
    p = p.replace("/_search_", "/_search")
    # angle/brace variables -> *
    p = re.sub(r"<[^>]+>", "*", p)
    p = re.sub(r"\{[^}]+\}", "*", p)

    cands = set()

    def finalize(x):
        x = re.sub(r"/+", "/", x)
        if len(x) > 1:
            x = x.rstrip("/")
        return x

    # Base candidate (keeps literal _all, e.g. PIT /_search/point_in_time/_all)
    cands.add(finalize(p))

    # snapshot list-all: under /_snapshot/, _all is a concrete {snapshot} value,
    # so add a variable-form candidate too (NOT a rewrite -- the literal form is
    # kept above for the PIT /_all path which the base models verbatim).
    if p.startswith("/_snapshot/") and "/_all" in p:
        cands.add(finalize(p.replace("/_all", "/*")))

    # _mappings -> _mapping (also cover a bare /_mappings and /*/_mappings)
    if "_mappings" in p:
        cands.add(finalize(p.replace("_mappings", "_mapping")))
    # /_setting singular (word boundary, not _settings) -> /_settings
    if re.search(r"_setting(?![s])", p):
        cands.add(finalize(re.sub(r"_setting(?![s])", "_settings", p)))
    # glued pipeline variable: "/_search/pipeline*" -> also "/_search/pipeline"
    if "pipeline*" in p:
        cands.add(finalize(p.replace("pipeline*", "pipeline")))
        cands.add(finalize(p.replace("pipeline*", "pipeline/*")))
    # trailing-slash-with-no-variable (e.g. .../models/): parser dropped a var
    if parser_path.split("?", 1)[0].rstrip().endswith("/"):
        cands.add(finalize(p.rstrip("/") + "/*"))

    return {c for c in cands if c}


def normalize_base(base_path):
    """Normalize an OpenAPI base path: every {param} -> *."""
    p = re.sub(r"\{[^}]+\}", "*", base_path)
    p = re.sub(r"/+", "/", p)
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("allowlist_md")
    ap.add_argument("base_spec")
    ap.add_argument("out_overlay")
    ap.add_argument("--report", action="store_true", help="print diagnostics only, do not require zero unmatched")
    args = ap.parse_args()

    entries = parse_allowlist(args.allowlist_md)
    # Build the ALLOW set of normalized paths (union of all candidate forms),
    # skipping excluded rows.
    allow_paths = set()    # every candidate norm_path across kept rows
    row_cands = []         # (parser_path, set(candidates)) for kept rows, for the invariant
    kept_rows = 0
    excluded_rows = 0
    for methods, path, excluded in entries:
        if excluded:
            excluded_rows += 1
            continue
        kept_rows += 1
        cands = normalize(path)
        row_cands.append((path, cands))
        allow_paths |= cands

    base = yaml.safe_load(Path(args.base_spec).read_text())
    base_paths = base.get("paths", {})

    base_norm = set()      # set of norm_path present in base
    for real_path, item in base_paths.items():
        base_norm.add(normalize_base(real_path))

    # Parser rows that the OSS spec genuinely does not model as a standalone
    # path item (verified against base). Acknowledged, not silently dropped:
    # they are undocumented sub-queries hung off a modeled parent, so they add
    # NO base path to keep and cannot drift the removes.
    KNOWN_UNMODELED = {
        "/_plugins/_flow_framework/workflow/_status",   # status query, not a modeled path
        "/_plugins/_flow_framework/workflow/_step",     # single-step query, not modeled
        "/_plugins/_ml/memory_containers/*/memories/sessions/_search",  # deep undoc combo
    }

    # INVARIANT: every kept row must have >=1 candidate in base OR be KNOWN_UNMODELED.
    unmatched = []
    for parser_path, cands in row_cands:
        if cands & base_norm:
            continue
        # try KNOWN_UNMODELED against any candidate
        if cands & KNOWN_UNMODELED:
            continue
        unmatched.append((parser_path, sorted(cands)))

    # Decide removes: keep a base path iff its norm form is in allow_paths.
    removes = []
    kept_base_paths = 0
    for real_path, item in base_paths.items():
        if normalize_base(real_path) in allow_paths:
            kept_base_paths += 1
        else:
            removes.append(real_path)

    print(f"allowlist rows: kept={kept_rows} excluded(lock)={excluded_rows}")
    print(f"allow norm-paths: {len(allow_paths)}")
    print(f"base: {len(base_paths)} paths")
    print(f"KEEP base paths: {kept_base_paths}   REMOVE base paths: {len(removes)}")
    print()
    if unmatched:
        print(f"!! INVARIANT VIOLATION: {len(unmatched)} allowlist rows matched NO base path and are not KNOWN_UNMODELED:")
        for pp, cands in unmatched:
            print(f"   - {pp}   candidates={cands}")
        print("   (parser-path typo, OSS-spec gap, or AOSS-only path needing an extension overlay)")
        print()

    if unmatched and not args.report:
        print("ABORT: resolve unmatched allowlist rows (fix normalization, add to KNOWN_UNMODELED with a reason, or move to an extension overlay).", file=sys.stderr)
        sys.exit(2)

    # Emit overlay
    overlay = {
        "overlay": "1.0.0",
        "info": {
            "title": "Amazon OpenSearch Serverless - API Surface Overlay (allowlist-generated)",
            "version": "2026.09.03",
        },
        "actions": [
            {"target": f"$.paths['{rp}']", "remove": True} for rp in sorted(removes)
        ],
    }
    if not args.report:
        Path(args.out_overlay).write_text(
            yaml.safe_dump(overlay, sort_keys=False, default_flow_style=False, width=200)
        )
        print(f"wrote {args.out_overlay}: {len(removes)} remove actions")


if __name__ == "__main__":
    main()
