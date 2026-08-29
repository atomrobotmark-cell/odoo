#!/usr/bin/env bash
#
# WAHA Docker build helper (GOWS engine, no Chromium)
# ----------------------------------------------------
# Clones the official WAHA source, overlays our custom build files from this
# folder, then builds the `waha-gows:local` image.
#
# This automates the documented flow so the whole build is reproducible from
# this repo alone. The only external input is the public WAHA source (fetched
# by this script), which provides yarn.lock / .yarnrc.yml / entrypoint.sh etc.
#
# Usage:
#   ./build.sh                 # build with default proxy (192.168.140.175:10809)
#   PROXY=http://host:port ./build.sh
#   WAHA_REF=v2024.12 ./build.sh     # pin a WAHA source tag/branch/commit
#   WAHA_SRC=/path/to/existing/waha-src ./build.sh   # reuse a local clone (offline)
#
set -euo pipefail

# ---- configurable values -------------------------------------------------
WAHA_REPO="${WAHA_REPO:-https://github.com/devlikeapro/waha.git}"
WAHA_REF="${WAHA_REF:-main}"                 # pin for reproducible builds
PROXY="${PROXY:-http://192.168.140.175:10809}"
IMAGE_TAG="${IMAGE_TAG:-waha-gows:local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- prepare a working copy of WAHA source -------------------------------
if [[ -n "${WAHA_SRC:-}" && -d "$WAHA_SRC" ]]; then
  echo "==> Using existing WAHA source at: $WAHA_SRC"
  SRC="$WAHA_SRC"
else
  SRC="$(mktemp -d)"
  echo "==> Cloning WAHA source ($WAHA_REF) into: $SRC"
  git clone --depth 1 --branch "$WAHA_REF" "$WAHA_REPO" "$SRC" \
    || git clone "$WAHA_REPO" "$SRC"
  if [[ "$WAHA_REF" != "main" ]]; then
    git -C "$SRC" fetch origin "$WAHA_REF" && git -C "$SRC" checkout "$WAHA_REF"
  fi
fi

# ---- overlay our custom build files --------------------------------------
echo "==> Overlaying custom build files from: $SCRIPT_DIR"
cp "$SCRIPT_DIR/Dockerfile"       "$SRC/Dockerfile"
cp "$SCRIPT_DIR/package.json"     "$SRC/package.json"
cp "$SCRIPT_DIR/waha.config.json" "$SRC/waha.config.json"
cp "$SCRIPT_DIR/.dockerignore"    "$SRC/.dockerignore"
# NOTE: yarn.lock and .yarnrc.yml come from the WAHA source clone above.

# ---- build ---------------------------------------------------------------
echo "==> Building image: $IMAGE_TAG (GOWS engine, USE_BROWSER=none)"
docker build \
  --build-arg HTTP_PROXY="$PROXY" \
  --build-arg HTTPS_PROXY="$PROXY" \
  --build-arg USE_BROWSER=none \
  --build-arg WHATSAPP_DEFAULT_ENGINE=gows \
  -t "$IMAGE_TAG" \
  "$SRC"

echo "==> Done. Start it with: ./waha_run.sh"
echo "    (or: docker run -d --name waha -p 3000:3000 -e WHATSAPP_DEFAULT_ENGINE=GOWS -e WAHA_API_KEY=<key> $IMAGE_TAG)"
