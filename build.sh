#!/bin/bash
# Builds "Quick Event.alfredworkflow" from the workflow/ folder.
set -e
cd "$(dirname "$0")"
find workflow -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
plutil -lint workflow/info.plist >/dev/null
rm -f "Quick Event.alfredworkflow"
(cd workflow && zip -qr "../Quick Event.alfredworkflow" . -x '.DS_Store')
echo "Built: Quick Event.alfredworkflow"
