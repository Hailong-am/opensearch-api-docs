#!/usr/bin/env bash
# Build distribution-specific OpenAPI specs from YAML + overlays.
#
# SINGLE SOURCE OF TRUTH: this repository (overlays + tools). The OSS BASE spec
# is fetched fresh from the canonical upstream URL at build time so all three
# distributions track the latest published OpenSearch API surface:
#
#   - Base OSS spec:      $OSS_SPEC_URL  (default: api-spec.opensearch.org),
#                         cached to spec/opensearch-openapi.yaml as a fallback
#   - Blocklist overlays:  overlays/amazon-managed.overlay.yaml, overlays/amazon-serverless.overlay.yaml
#   - Extension overlays:  overlays/aos-extensions.overlay.yaml (UltraWarm + Cold, AOS-only),
#                          overlays/aoss-snapshot-api-extensions.overlay.yaml
#   - Constraint overlays: overlays/aoss-refresh-constraint.overlay.yaml
#   - Tools:               tools/inject-tags.py, tools/strip-deprecated.py
#
# All local paths are repo-relative. No home-dir dependencies. No ad-hoc JSON edits.
#
# Usage:  ./tools/build-distribution-specs.sh   (run from repo root or anywhere)
#   OSS_SPEC_URL=<url>  override the upstream base spec URL
#   OFFLINE=1           skip the fetch, use the cached spec/opensearch-openapi.yaml
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPEC_DIR="$REPO_DIR/spec"
OVERLAYS_DIR="$REPO_DIR/overlays"
TOOLS_DIR="$REPO_DIR/tools"
BUILD_DIR="$REPO_DIR/build"

OSS_SPEC_URL="${OSS_SPEC_URL:-https://api-spec.opensearch.org/opensearch-openapi.yaml}"
CACHED_SPEC="$SPEC_DIR/opensearch-openapi.yaml"
BASE_SPEC="$BUILD_DIR/opensearch-openapi.yaml"

mkdir -p "$BUILD_DIR"

echo "=== Building distribution specs from YAML + overlays ==="
echo "Repo:      $REPO_DIR"

# --- Resolve the OSS base spec: fetch upstream, fall back to cached copy ---
echo ""
echo "--- Base spec ---"
if [ "${OFFLINE:-0}" = "1" ]; then
  echo "  OFFLINE=1: using cached $CACHED_SPEC"
  cp "$CACHED_SPEC" "$BASE_SPEC"
elif curl -fsSL "$OSS_SPEC_URL" -o "$BASE_SPEC"; then
  echo "  Fetched upstream: $OSS_SPEC_URL ($(wc -c < "$BASE_SPEC") bytes)"
  # Refresh the in-repo cache so an offline build stays reproducible.
  cp "$BASE_SPEC" "$CACHED_SPEC"
else
  echo "  WARN: upstream fetch failed ($OSS_SPEC_URL); falling back to cached $CACHED_SPEC" >&2
  cp "$CACHED_SPEC" "$BASE_SPEC"
fi
echo "Base spec: $BASE_SPEC"

# --- OSS: base spec, no overlay ---
echo ""
echo "--- OSS ---"
cp "$BASE_SPEC" "$BUILD_DIR/opensearch-openapi-oss.yaml"

# All overlays are applied with the speakeasy overlay CLI (single tool). It
# supports $ref filter predicates (which openapi-overlays-js rejected), so the
# whole pipeline is standardized on it. Install:
#   https://github.com/speakeasy-api/speakeasy (prebuilt binary; no Go needed)
: "${SPEAKEASY:=speakeasy}"
if ! command -v "$SPEAKEASY" >/dev/null 2>&1; then
  echo "ERROR: '$SPEAKEASY' not found on PATH. Overlays are applied with the" >&2
  echo "       speakeasy overlay CLI. Install it or set SPEAKEASY=/path/to/speakeasy." >&2
  echo "       See README." >&2
  exit 3
fi

# --- AOS: remove overlay + AOS-only extensions (UltraWarm + Cold tier) ---
echo ""
echo "--- AOS ---"
echo "  Step 1: Apply remove overlay (blocklist)"
"$SPEAKEASY" overlay apply \
  --schema "$BASE_SPEC" \
  --overlay "$OVERLAYS_DIR/amazon-managed.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos.yaml"

echo "  Step 2: Apply AOS-only extensions overlay (UltraWarm + Cold tier)"
"$SPEAKEASY" overlay apply \
  --schema "$BUILD_DIR/opensearch-openapi-aos.yaml" \
  --overlay "$OVERLAYS_DIR/aos-extensions.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos-full.yaml"

# --- AOSS: allowlist overlay (generated) + snapshot extension + unsettable + refresh strip ---
echo ""
echo "--- AOSS ---"
echo "  Step 0: Regenerate allowlist overlay from the DP API allowlist + current base"
# ALLOWLIST strategy: overlays/amazon-serverless-allowlist.overlay.yaml is a
# GENERATED artifact -- every base (path) not covered by the customer-facing DP
# API allowlist (spec/aoss-dp-api-allowlist.md, from parser V2 doc/APIs.md) is
# removed. Regenerating here keeps the overlay in lockstep with the base fetched
# above; CI enforces `regenerate && git diff --exit-code` (idempotency gate).
python3 "$TOOLS_DIR/generate-aoss-allowlist.py" \
  "$SPEC_DIR/aoss-dp-api-allowlist.md" \
  "$BASE_SPEC" \
  "$OVERLAYS_DIR/amazon-serverless-allowlist.overlay.yaml"

echo "  Step 1: Apply allowlist overlay (remove everything not in the allowlist)"
"$SPEAKEASY" overlay apply \
  --schema "$BASE_SPEC" \
  --overlay "$OVERLAYS_DIR/amazon-serverless-allowlist.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss.yaml"

echo "  Step 2: Apply snapshot extension overlay (AOSS body fields on the kept snapshot paths)"
"$SPEAKEASY" overlay apply \
  --schema "$BUILD_DIR/opensearch-openapi-aoss.yaml" \
  --overlay "$OVERLAYS_DIR/aoss-snapshot-api-extensions.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss-snap.yaml"

echo "  Step 3: Remove structurally-unsettable index settings (number_of_shards / number_of_replicas)"
# These two have NO per-account dynamic-config escape hatch -- no account can
# ever set them (the collection owns shard/replica topology), so they are the
# only index SETTINGS removed from the AOSS schema. Account-conditional settings
# (refresh_interval, warm.after, kNN opts, timestamp_field) are left in
# deliberately -- a per-account override can enable them.
"$SPEAKEASY" overlay apply \
  --schema "$BUILD_DIR/opensearch-openapi-aoss-snap.yaml" \
  --overlay "$OVERLAYS_DIR/aoss-unsettable-index-settings-remove.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss-unsettable.yaml"

echo "  Step 4: Apply refresh-removal overlay"
# `refresh` is rejected for EVERY account (no dynamic-config override exists), so
# like shards/replicas it is genuinely non-settable and removed from the AOSS
# surface. Uses $ref filter predicates -> speakeasy (already the pipeline tool).
"$SPEAKEASY" overlay apply \
  --schema "$BUILD_DIR/opensearch-openapi-aoss-unsettable.yaml" \
  --overlay "$OVERLAYS_DIR/aoss-refresh-remove.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss-full.yaml"
# NOTE: the old empirical-behavior blocklist (reindex / update_by_query /
# delete_by_query + rethrottles) is now REDUNDANT -- none of those paths are in
# the allowlist, so Step 1 already removes them. Overlay retired.

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
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-aoss-full.json" "$BUILD_DIR/opensearch-openapi-aoss-clean.json" --no-version

echo ""
echo "--- Inject tags ---"
python3 "$TOOLS_DIR/inject-tags.py" "$BUILD_DIR/opensearch-openapi-oss-clean.json"  "$BUILD_DIR/opensearch-openapi-oss-tagged.json"
python3 "$TOOLS_DIR/inject-tags.py" "$BUILD_DIR/opensearch-openapi-aos-clean.json"  "$BUILD_DIR/opensearch-openapi-aos-tagged.json"
python3 "$TOOLS_DIR/inject-tags.py" "$BUILD_DIR/opensearch-openapi-aoss-clean.json" "$BUILD_DIR/opensearch-openapi-aoss-tagged.json"

echo ""
echo "=== Done ==="
echo "Output files:"
ls -lh "$BUILD_DIR"/*-tagged.json
