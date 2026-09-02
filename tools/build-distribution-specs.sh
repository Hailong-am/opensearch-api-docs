#!/usr/bin/env bash
# Build distribution-specific OpenAPI specs from YAML + overlays.
#
# SINGLE SOURCE OF TRUTH: this repository.
#   - Base OSS spec:      spec/opensearch-openapi.yaml
#   - Blocklist overlays:  overlays/amazon-managed.overlay.yaml, overlays/amazon-serverless.overlay.yaml
#   - Extension overlays:  overlays/aoss-ultrawarm-api.overlay.yaml, overlays/aos-cold-api.overlay.yaml,
#                          overlays/aoss-snapshot-api-extensions.overlay.yaml
#   - Tools:               tools/inject-tags.py, tools/strip-deprecated.py
#
# All paths are repo-relative. No external/home-dir dependencies. No ad-hoc JSON edits.
#
# Usage:  ./tools/build-distribution-specs.sh   (run from repo root or anywhere)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPEC_DIR="$REPO_DIR/spec"
OVERLAYS_DIR="$REPO_DIR/overlays"
TOOLS_DIR="$REPO_DIR/tools"
BUILD_DIR="$REPO_DIR/build"

BASE_SPEC="$SPEC_DIR/opensearch-openapi.yaml"

mkdir -p "$BUILD_DIR"

echo "=== Building distribution specs from YAML + overlays ==="
echo "Repo:      $REPO_DIR"
echo "Base spec: $BASE_SPEC"

# --- OSS: base spec, no overlay ---
echo ""
echo "--- OSS ---"
cp "$BASE_SPEC" "$BUILD_DIR/opensearch-openapi-oss.yaml"

# --- AOS: remove overlay + UltraWarm extension + Cold tier extension ---
echo ""
echo "--- AOS ---"
echo "  Step 1: Apply remove overlay (blocklist)"
npx openapi-overlays-js \
  --openapi "$BASE_SPEC" \
  --overlay "$OVERLAYS_DIR/amazon-managed.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos.yaml"

echo "  Step 2: Apply UltraWarm extension overlay"
npx openapi-overlays-js \
  --openapi "$BUILD_DIR/opensearch-openapi-aos.yaml" \
  --overlay "$OVERLAYS_DIR/aoss-ultrawarm-api.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos-warm.yaml"

echo "  Step 3: Apply Cold tier extension overlay"
npx openapi-overlays-js \
  --openapi "$BUILD_DIR/opensearch-openapi-aos-warm.yaml" \
  --overlay "$OVERLAYS_DIR/aos-cold-api.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos-full.yaml"

# --- AOSS: remove overlay + snapshot extension ---
echo ""
echo "--- AOSS ---"
echo "  Step 1: Apply remove overlay (blocklist)"
npx openapi-overlays-js \
  --openapi "$BASE_SPEC" \
  --overlay "$OVERLAYS_DIR/amazon-serverless.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss.yaml"

echo "  Step 2: Apply snapshot extension overlay"
npx openapi-overlays-js \
  --openapi "$BUILD_DIR/opensearch-openapi-aoss.yaml" \
  --overlay "$OVERLAYS_DIR/aoss-snapshot-api-extensions.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss-full.yaml"

# --- Convert YAML -> JSON ---
echo ""
echo "=== Post-processing ==="
python3 -c "
import yaml, json
for name in ['opensearch-openapi-oss', 'opensearch-openapi-aos-full', 'opensearch-openapi-aoss-full']:
    with open(f'$BUILD_DIR/{name}.yaml') as f:
        data = yaml.safe_load(f)
    with open(f'$BUILD_DIR/{name}.json', 'w') as f:
        json.dump(data, f)
    print(f'  {name}: {len(data.get(\"paths\", {}))} paths -> JSON')
"

echo ""
echo "--- Strip deprecated ---"
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-oss.json"       "$BUILD_DIR/opensearch-openapi-oss-clean.json"
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-aos-full.json"  "$BUILD_DIR/opensearch-openapi-aos-clean.json"
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-aoss-full.json" "$BUILD_DIR/opensearch-openapi-aoss-clean.json"

echo ""
echo "--- Inject tags ---"
python3 "$TOOLS_DIR/inject-tags.py" "$BUILD_DIR/opensearch-openapi-oss-clean.json"  "$BUILD_DIR/opensearch-openapi-oss-tagged.json"
python3 "$TOOLS_DIR/inject-tags.py" "$BUILD_DIR/opensearch-openapi-aos-clean.json"  "$BUILD_DIR/opensearch-openapi-aos-tagged.json"
python3 "$TOOLS_DIR/inject-tags.py" "$BUILD_DIR/opensearch-openapi-aoss-clean.json" "$BUILD_DIR/opensearch-openapi-aoss-tagged.json"

echo ""
echo "=== Done ==="
echo "Output files:"
ls -lh "$BUILD_DIR"/*-tagged.json
