# OpenSearch API Docs

Distribution-specific OpenSearch API reference (OSS / AOS / AOSS), rendered with
[Scalar](https://github.com/scalar/scalar) and published to GitHub Pages.

**This repository is the single source of truth** for the OSS base spec, the
distribution overlays, and the build tooling. No external / home-directory
dependencies — clone it and everything needed to rebuild the specs is here.

Live: https://hailong-am.github.io/opensearch-api-docs/
- `?dist=oss`  — OpenSearch (OSS), 696 operations
- `?dist=aos`  — Amazon OpenSearch Service, 683 operations (+ UltraWarm + Cold Tier)
- `?dist=aoss` — Amazon OpenSearch Serverless, 605 operations (+ snapshot extensions)

## Layout

```
index.html                 Scalar renderer; ?dist= selects the spec
package.json               pins openapi-overlays-js
spec/
  opensearch-openapi.yaml  OSS base spec (hand-authored upstream, YAML)
overlays/
  amazon-managed.overlay.yaml              AOS blocklist (remove-only)
  amazon-serverless.overlay.yaml           AOSS blocklist (remove-only)
  aoss-ultrawarm-api.overlay.yaml          AOS UltraWarm additions
  aos-cold-api.overlay.yaml                AOS Cold Tier additions
  aoss-snapshot-api-extensions.overlay.yaml AOSS snapshot additions
tools/
  build-distribution-specs.sh  the build (all paths repo-relative)
  strip-deprecated.py          removes deprecated ops, injects "Minimum version"
  inject-tags.py               maps x-operation-group prefixes to Scalar sidebar groups
build/                        generated output (git-tracked; the site loads *-tagged.json)
```

## Build

```bash
npm install                       # installs pinned openapi-overlays-js
npm run build                     # == ./tools/build-distribution-specs.sh
```

Pipeline per distribution:

```
spec/opensearch-openapi.yaml
  ──apply blocklist + extension overlays (openapi-overlays-js)──▶  *-full.yaml
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

- Node.js (for `npx openapi-overlays-js`)
- Python 3 with PyYAML (`pip install pyyaml`)
