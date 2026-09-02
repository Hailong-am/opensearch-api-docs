#!/usr/bin/env python3
"""Remove the write-op `refresh` query parameter from an AOSS spec.

Amazon OpenSearch Serverless rejects every explicit refresh value
(refresh=true and refresh=wait_for both return
400 "<value> refresh policy is not supported"; only the default false works),
so the parameter is meaningless on AOSS and is removed entirely.

This is done as a post-processing step (not an OpenAPI overlay) because it must
delete BOTH the shared component parameter definitions AND every operation-level
`$ref` that points at them -- array-element surgery that JSONPath overlays do
not do reliably. Leaving a dangling $ref would break the Scalar renderer.

Scope: only components/parameters whose name == "refresh" and in == "query"
(the write-op refresh policy). The indices.refresh___* params belong to the
`_refresh` API endpoint and are left untouched.

Usage: strip-refresh.py <input.json> <output.json>
"""
import json
import sys


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    with open(src) as f:
        spec = json.load(f)

    params = spec.get("components", {}).get("parameters", {})

    # 1. Identify the refresh query-param component keys.
    refresh_keys = {
        k for k, v in params.items()
        if isinstance(v, dict) and v.get("name") == "refresh" and v.get("in") == "query"
    }
    refresh_suffixes = tuple(f"/{k}" for k in refresh_keys)

    def is_refresh_ref(p: dict) -> bool:
        ref = p.get("$ref", "") if isinstance(p, dict) else ""
        return ref.endswith(refresh_suffixes)

    # 2. Strip operation-level $refs to those params.
    removed_refs = 0
    for methods in spec.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for op in methods.values():
            if not isinstance(op, dict) or "parameters" not in op:
                continue
            before = len(op["parameters"])
            op["parameters"] = [p for p in op["parameters"] if not is_refresh_ref(p)]
            removed_refs += before - len(op["parameters"])

    # 3. Remove the component parameter definitions.
    for k in refresh_keys:
        params.pop(k, None)

    with open(dst, "w") as f:
        json.dump(spec, f)

    print(f"  Removed {len(refresh_keys)} refresh param defs, {removed_refs} operation $refs")
    print(f"  Written: {dst}")


if __name__ == "__main__":
    main()
