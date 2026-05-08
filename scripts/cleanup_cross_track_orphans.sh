#!/usr/bin/env bash
# cleanup_cross_track_orphans.sh
#
# Cross-track orphan cleanup
# Removes {cache_root}/cross-track-*/ dirs older than 7 days.
#
# Default cache root: ./_autonomous/cross-track-cache/
# Override via --cache-root PATH or CROSS_TRACK_CACHE_ROOT env var.
#
# Usage:
#   bash cleanup_cross_track_orphans.sh [--dry-run] [--cache-root PATH]

set -euo pipefail

DRY_RUN=false
CACHE_ROOT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --cache-root)
            CACHE_ROOT="$2"
            shift 2
            ;;
        --cache-root=*)
            CACHE_ROOT="${1#--cache-root=}"
            shift
            ;;
        *)
            echo "Unknown arg: $1" >&2
            echo "Usage: bash $0 [--dry-run] [--cache-root PATH]" >&2
            exit 2
            ;;
    esac
done

if [[ -z "${CACHE_ROOT}" ]]; then
    CACHE_ROOT="${CROSS_TRACK_CACHE_ROOT:-$(pwd)/_autonomous/cross-track-cache}"
fi

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[cleanup_cross_track_orphans] DRY-RUN mode - no files deleted."
fi

if [[ ! -d "${CACHE_ROOT}" ]]; then
    echo "[cleanup_cross_track_orphans] Cache root does not exist: ${CACHE_ROOT}"
    exit 0
fi

FOUND=0

while IFS= read -r -d '' dir; do
    FOUND=$((FOUND + 1))
    echo "[cleanup_cross_track_orphans] Removing orphan dir (>7 days): ${dir}"
    if [[ "${DRY_RUN}" == "false" ]]; then
        rm -rf "${dir}"
    fi
done < <(find "${CACHE_ROOT}" \
    -maxdepth 1 \
    -type d \
    -name "cross-track-*" \
    -mtime +7 \
    -print0)

if [[ "${FOUND}" -eq 0 ]]; then
    echo "[cleanup_cross_track_orphans] No orphan cross-track dirs >7 days found in ${CACHE_ROOT}"
else
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "[cleanup_cross_track_orphans] DRY-RUN: would remove ${FOUND} dir(s)."
    else
        echo "[cleanup_cross_track_orphans] Removed ${FOUND} orphan dir(s)."
    fi
fi
