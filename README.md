# OpenSearch API Docs

Distribution-specific OpenSearch API reference (OSS / AOS / AOSS), rendered with
[Scalar](https://github.com/scalar/scalar) and published to GitHub Pages.

**This repository is the single source of truth** for the OSS base spec, the
distribution overlays, and the build tooling. No external / home-directory
dependencies — clone it and everything needed to rebuild the specs is here.

Live: https://hailong-am.github.io/opensearch-api-docs/
- `?dist=oss`  — OpenSearch (OSS), 696 operations
- `?dist=aos`  — Amazon OpenSearch Service, 683 operations (+ UltraWarm + Cold Tier)
- `?dist=aoss` — Amazon OpenSearch Serverless, 176 operations (allowlist-generated from the customer-facing DP API surface + snapshot extensions)

## Layout

```
index.html                 Scalar renderer; ?dist= selects the spec
package.json               build script entry (no npm overlay dep; overlays use speakeasy)
spec/
  opensearch-openapi.yaml  OSS base spec (cached upstream copy; fetched fresh at build time)
  aoss-dp-api-allowlist.md  AOSS customer-facing DP API allowlist (SOURCE OF TRUTH for AOSS;
                            from parser V2 doc/APIs.md). Drives the generated AOSS overlay.
overlays/
  amazon-managed.overlay.yaml               AOS blocklist (remove-only, hand-maintained)
  amazon-serverless-allowlist.overlay.yaml  AOSS surface (GENERATED — do not hand-edit;
                                            everything not in the allowlist is removed)
  aos-extensions.overlay.yaml               AOS UltraWarm + Cold Tier additions
  aoss-snapshot-api-extensions.overlay.yaml AOSS snapshot body-field additions
  aoss-unsettable-index-settings-remove.overlay.yaml
                                            (AOSS) removes number_of_shards / number_of_replicas
                                            from IndexSettings — the only two index settings with
                                            NO per-account dynamic-config override (the collection
                                            owns topology). Account-conditional settings
                                            (refresh_interval, warm.after, kNN opts, timestamp_field)
                                            are deliberately LEFT IN — a per-account override can
                                            enable them, so a static removal would be wrong.
  aoss-refresh-remove.overlay.yaml          (AOSS) strips the write-op refresh param — rejected
                                            for EVERY account (400), no override exists
tools/
  build-distribution-specs.sh  the build (all paths repo-relative)
  generate-aoss-allowlist.py   regenerates the AOSS allowlist overlay from the allowlist md
                               + current base; hard invariant: every allowlist row must match
                               a base path. CI gates `regenerate && git diff --exit-code`.
  strip-deprecated.py          removes deprecated ops, injects "Minimum version"
  inject-tags.py               maps x-operation-group prefixes to Scalar sidebar groups
build/                        generated output (git-tracked; the site loads *-tagged.json)
```

## Build

```bash
npm run build                     # == ./tools/build-distribution-specs.sh
```

All overlays are applied with the **speakeasy overlay CLI** (a single tool for
the whole pipeline). speakeasy supports `$ref` filter predicates, which the
previously-used `openapi-overlays-js` rejected; standardizing on it removes the
split-tool complexity and the npm dependency. Install the prebuilt binary (no
Go needed): https://github.com/speakeasy-api/speakeasy — set
`SPEAKEASY=/path/to/speakeasy` if it is not on `PATH`.

Pipeline per distribution:

```
spec/opensearch-openapi.yaml
  ──apply blocklist / allowlist + extension overlays (speakeasy)──▶  *-full.yaml
  ──YAML→JSON──▶  *.json
  ──strip-deprecated.py──▶  *-clean.json
  ──inject-tags.py──▶  *-tagged.json   ◀── index.html loads this
```

The `*-tagged.json` files carry the `tags` metadata Scalar uses for the grouped
left-hand navigation. `*-clean.json` is the pre-tagging intermediate.

## Deploy

The `master`/`main` branch holds source; `gh-pages` serves the site. To publish,
copy `index.html` + `build/*-tagged.json` to the `gh-pages` branch (GitHub Pages
is served from `gh-pages`).

## Requirements

- speakeasy overlay CLI — applies ALL overlays (needs `$ref` filter support): https://github.com/speakeasy-api/speakeasy — prebuilt binary, no Go needed. Set `SPEAKEASY=/path` if not on `PATH`.
- Python 3 with PyYAML (`pip install pyyaml`)
