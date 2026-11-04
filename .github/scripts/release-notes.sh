#!/usr/bin/env bash
# Imprime el cuerpo de la sección "## [VERSIÓN]" de CHANGELOG.md, sin el título.
set -euo pipefail
awk -v heading="## [$1]" '
  /^## / { inside = (index($0, heading) == 1); next }
  inside
' CHANGELOG.md | sed -e '/./,$!d'
