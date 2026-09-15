#!/usr/bin/env bash
# Build distribution-specific OpenAPI specs from YAML + overlays.
#
# SINGLE SOURCE OF TRUTH: this repository (base spec + overlays + tools). The OSS
# BASE spec is the COMMITTED, version-controlled spec/opensearch-openapi.yaml.
# It already carries operation-level `tags` (from opensearch-api-specification
# PR #1242), which is what Scalar groups its sidebar by -- so the repo owns the
# tags and no tag-injection pass is needed. The build does NOT fetch upstream by
# default: the live api-spec.opensearch.org base is still untagged (PR #1242 not
# merged), so fetching it would strip the grouping. Pass REFRESH_BASE=1 to pull
# a fresh upstream base on purpose (e.g. once #1242 has merged upstream).
#
#   - Base OSS spec:      spec/opensearch-openapi.yaml  (COMMITTED, tagged; the default)
#   - AOS overlays:       overlays/aos/amazon-managed.overlay.yaml (blocklist),
#                         overlays/aos/aos-extensions.overlay.yaml (UltraWarm + Cold, AOS-only, tagged inline)
#   - AOSS overlays:      overlays/aoss/amazon-serverless-allowlist.overlay.yaml (GENERATED allowlist),
#                         overlays/aoss/aoss-extensions.overlay.yaml (hand-authored, merged: snapshot + index
#                         lifecycle additions, unsettable-settings + refresh removals)
#   - Tools:               tools/strip-deprecated.py (tags come from the base
#                          spec + the AOS extension overlay; no tag-injection pass)
#
# All local paths are repo-relative. No home-dir dependencies. No ad-hoc JSON edits.
#
# Usage:  ./tools/build-distribution-specs.sh   (run from repo root or anywhere)
#   REFRESH_BASE=1      pull a fresh upstream base from $OSS_SPEC_URL and OVERWRITE
#                       the committed spec/opensearch-openapi.yaml (use once upstream
#                       carries tags; otherwise it strips the sidebar grouping)
#   OSS_SPEC_URL=<url>  override the upstream base spec URL (only used with REFRESH_BASE=1)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPEC_DIR="$REPO_DIR/spec"
OVERLAYS_DIR="$REPO_DIR/overlays"
TOOLS_DIR="$REPO_DIR/tools"
BUILD_DIR="$REPO_DIR/build"

OSS_SPEC_URL="${OSS_SPEC_URL:-https://api-spec.opensearch.org/opensearch-openapi.yaml}"
COMMITTED_SPEC="$SPEC_DIR/opensearch-openapi.yaml"
BASE_SPEC="$BUILD_DIR/opensearch-openapi.yaml"

mkdir -p "$BUILD_DIR"

echo "=== Building distribution specs from YAML + overlays ==="
echo "Repo:      $REPO_DIR"

# --- Resolve the OSS base spec ---
# Default: use the COMMITTED, tagged spec/opensearch-openapi.yaml (the repo owns
# the tagged base). REFRESH_BASE=1 fetches a fresh upstream base and overwrites
# the committed spec -- only do this once upstream carries operation tags, else
# it strips the Scalar sidebar grouping.
echo ""
echo "--- Base spec ---"
if [ "${REFRESH_BASE:-0}" = "1" ]; then
  if curl -fsSL "$OSS_SPEC_URL" -o "$BASE_SPEC"; then
    echo "  REFRESH_BASE=1: fetched upstream: $OSS_SPEC_URL ($(wc -c < "$BASE_SPEC") bytes)"
    # Overwrite the committed base so the repo stays the source of truth.
    cp "$BASE_SPEC" "$COMMITTED_SPEC"
    echo "  Overwrote committed $COMMITTED_SPEC"
  else
    echo "  WARN: upstream fetch failed ($OSS_SPEC_URL); using committed $COMMITTED_SPEC" >&2
    cp "$COMMITTED_SPEC" "$BASE_SPEC"
  fi
else
  echo "  Using committed base: $COMMITTED_SPEC"
  cp "$COMMITTED_SPEC" "$BASE_SPEC"
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
  --overlay "$OVERLAYS_DIR/aos/amazon-managed.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos.yaml"

echo "  Step 2: Apply AOS-only extensions overlay (UltraWarm + Cold tier)"
"$SPEAKEASY" overlay apply \
  --schema "$BUILD_DIR/opensearch-openapi-aos.yaml" \
  --overlay "$OVERLAYS_DIR/aos/aos-extensions.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aos-full.yaml"

# --- AOSS: allowlist overlay (generated) + snapshot extension + unsettable + refresh strip ---
echo ""
echo "--- AOSS ---"
echo "  Step 0: Regenerate allowlist overlay from the DP API allowlist + current base"
# ALLOWLIST strategy: overlays/aoss/amazon-serverless-allowlist.overlay.yaml is a
# GENERATED artifact -- every base (path) not covered by the customer-facing DP
# API allowlist (spec/aoss-dp-api-allowlist.md, from parser V2 doc/APIs.md) is
# removed. Regenerating here keeps the overlay in lockstep with the base fetched
# above; CI enforces `regenerate && git diff --exit-code` (idempotency gate).
python3 "$TOOLS_DIR/generate-aoss-allowlist.py" \
  "$SPEC_DIR/aoss-dp-api-allowlist.md" \
  "$BASE_SPEC" \
  "$OVERLAYS_DIR/aoss/amazon-serverless-allowlist.overlay.yaml"

echo "  Step 1: Apply allowlist overlay (remove everything not in the allowlist)"
"$SPEAKEASY" overlay apply \
  --schema "$BASE_SPEC" \
  --overlay "$OVERLAYS_DIR/aoss/amazon-serverless-allowlist.overlay.yaml" \
  > "$BUILD_DIR/opensearch-openapi-aoss.yaml"

echo "  Step 2: Apply merged hand-authored AOSS overlays (snapshot + index-lifecycle"
echo "          extensions, unsettable-settings removal, refresh removal)"
# The four hand-authored AOSS overlays are merged into one aoss-extensions.overlay.yaml
# (removes-then-adds; disjoint JSONPath targets so a single pass is order-safe).
# The generated allowlist overlay (Step 1) stays separate so
# tools/generate-aoss-allowlist.py can still own it. Uses $ref filter predicates
# -> speakeasy (already the pipeline tool).
"$SPEAKEASY" overlay apply \
  --schema "$BUILD_DIR/opensearch-openapi-aoss.yaml" \
  --overlay "$OVERLAYS_DIR/aoss/aoss-extensions.overlay.yaml" \
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
echo "--- Strip deprecated (final render targets) ---"
# Tags now live in the base spec (upstream opensearch-api-specification carries
# operation-level tags on every operation) and in the AOS extension overlay
# (UltraWarm / Cold Tier ops tagged inline). No separate tag-injection pass is
# needed -- strip-deprecated writes the final *-tagged.json that index.html loads.
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-oss.json"       "$BUILD_DIR/opensearch-openapi-oss-tagged.json"
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-aos-full.json"  "$BUILD_DIR/opensearch-openapi-aos-tagged.json"
python3 "$TOOLS_DIR/strip-deprecated.py" "$BUILD_DIR/opensearch-openapi-aoss-full.json" "$BUILD_DIR/opensearch-openapi-aoss-tagged.json" --no-version

echo ""
echo "=== Done ==="
echo "Output files:"
ls -lh "$BUILD_DIR"/*-tagged.json
