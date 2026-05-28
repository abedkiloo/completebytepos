#!/usr/bin/env bash
#
# Assemble a runnable CompleteByte POS workspace from separate be + fe clones.
#
# Expected layout (any parent folder name):
#   <workspace>/
#     be/          ← backend repo (this script lives in be/__setup/)
#     fe/          ← frontend repo
#
# Usage (from anywhere):
#   ./be/__setup/assemble.sh
#   # or
#   cd be/__setup && ./assemble.sh
#
# Copies stack files from be/__setup/ → <workspace>/ without overwriting existing files.

set -euo pipefail

SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BE_DIR="$(cd "${SETUP_DIR}/.." && pwd)"
WORKSPACE_ROOT="$(cd "${BE_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[assemble]${NC} $*"; }
ok() { echo -e "${GREEN}[assemble]${NC} $*"; }
warn() { echo -e "${YELLOW}[assemble]${NC} $*"; }
err() { echo -e "${RED}[assemble]${NC} $*" >&2; }

# Files/dirs in __setup that must NOT be copied to workspace root
SKIP_NAMES=(
  assemble.sh
  README.md
  MANIFEST
)

chmod_scripts_in_root() {
  for f in "${WORKSPACE_ROOT}"/*.sh; do
    [[ -f "$f" ]] && chmod +x "$f"
  done
}

should_skip() {
  local base="$1"
  for s in "${SKIP_NAMES[@]}"; do
    [[ "$base" == "$s" ]] && return 0
  done
  return 1
}

copy_item() {
  local name="$1"
  local src="${SETUP_DIR}/${name}"
  local dest="${WORKSPACE_ROOT}/${name}"

  if should_skip "$name"; then
    return 0
  fi

  if [[ ! -e "$src" ]]; then
    warn "missing in __setup (skipped): ${name}"
    return 0
  fi

  if [[ -e "$dest" ]]; then
    warn "exists, not overwriting: ${name}"
    return 0
  fi

  if [[ -d "$src" ]]; then
    cp -R "$src" "$dest"
  else
    cp "$src" "$dest"
  fi

  ok "copied: ${name}"
}

main() {
  info "Setup source:  ${SETUP_DIR}"
  info "Backend repo:  ${BE_DIR}"
  info "Workspace:     ${WORKSPACE_ROOT}"
  echo ""

  if [[ ! -f "${BE_DIR}/manage.py" ]]; then
    err "be/ does not look like the Django repo (manage.py missing)."
    err "Run this from a workspace that contains be/ and fe/ as siblings."
    exit 1
  fi

  if [[ ! -f "${WORKSPACE_ROOT}/fe/package.json" ]]; then
    err "fe/ repo not found at: ${WORKSPACE_ROOT}/fe"
    err "Clone the frontend repo as a sibling of be/, then run assemble again."
    exit 1
  fi

  local copied=0
  local skipped=0

  shopt -s dotglob nullglob
  for entry in "${SETUP_DIR}"/*; do
    name="$(basename "$entry")"
    if should_skip "$name"; then
      continue
    fi
    if [[ -e "${WORKSPACE_ROOT}/${name}" ]]; then
      warn "exists, not overwriting: ${name}"
      skipped=$((skipped + 1))
    else
      copy_item "$name"
      copied=$((copied + 1))
    fi
  done
  shopt -u dotglob nullglob

  chmod_scripts_in_root

  echo ""
  ok "Done. Copied ${copied} item(s), skipped ${skipped} existing."
  echo ""
  info "Next steps:"
  echo "  cd \"${WORKSPACE_ROOT}\""
  echo "  ./run_docker.sh          # dev"
  echo "  ./run_docker.sh --prod   # production build"
  echo "  ./check_data.sh          # optional data check"
}

main "$@"
