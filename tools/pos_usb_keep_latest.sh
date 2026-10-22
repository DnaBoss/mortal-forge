#!/usr/bin/env bash
# Keep only one NewRetail POS installer folder on the USB drive (user rule 2026-10-12:
# the USB keeps the last version only; older ones live in GitHub history).
#
# Usage: bash ~/tools/pos_usb_keep_latest.sh <folder-to-keep> [usb-root]
#   folder-to-keep  name of the folder that stays, e.g. NewRetail-POS-v0.1.7
#   usb-root        defaults to /run/media/cash/Ventoy
# Deletes every other top-level folder whose name starts with "NewRetail-POS" under usb-root.
# Prints each folder before deleting it. Touches nothing else on the drive.
# DRY_RUN=1 only prints what would be removed.
set -euo pipefail

keep="${1:?usage: pos_usb_keep_latest.sh <folder-to-keep> [usb-root]}"
root="${2:-/run/media/cash/Ventoy}"

[ -d "$root" ] || { echo "USB root not found: $root" >&2; exit 1; }
[ -d "$root/$keep" ] || { echo "folder to keep not found: $root/$keep" >&2; exit 1; }
[ -f "$root/$keep/SHA256SUMS.txt" ] || { echo "folder to keep has no SHA256SUMS.txt: $root/$keep" >&2; exit 1; }

removed=0
for dir in "$root"/NewRetail-POS*; do
  [ -d "$dir" ] || continue
  [ "$(basename "$dir")" = "$keep" ] && continue
  echo "removing $dir"
  [ "${DRY_RUN:-0}" = 1 ] || rm -r -- "$dir"
  removed=$((removed + 1))
done
verb="removed"; [ "${DRY_RUN:-0}" = 1 ] && verb="would remove (dry run)"
echo "kept $root/$keep; $verb $removed folder(s)"
ls -1 "$root"
