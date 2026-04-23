#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.local/bin"
TARGET="${TARGET_DIR}/nic"

mkdir -p "${TARGET_DIR}"
ln -sf "${REPO_ROOT}/scripts/nic" "${TARGET}"

echo "Installed nic launcher at ${TARGET}"
echo "Make sure ${TARGET_DIR} is in your PATH."

