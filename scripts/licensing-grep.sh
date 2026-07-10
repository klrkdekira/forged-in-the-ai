#!/usr/bin/env bash
# Fails if a forbidden core-book term (NOTICE.md content policy) appears in a
# tracked file outside the docs that are allowed to name it while describing
# the policy itself.
set -euo pipefail
cd "$(dirname "$0")/.."

forbidden='Doskvol|Duskwall'
# Docs describing the content policy are allowed to name the forbidden
# terms; code, packs, and fixtures are not.
allowlist='^(NOTICE\.md|CLAUDE\.md|README\.md|packs/README\.md|SPECIFICATION\.md|docs/.*\.md|scripts/licensing-grep\.sh)$'

hit_file="$(mktemp)"
trap 'rm -f "$hit_file"' EXIT

hits=0
while IFS= read -r file; do
  [[ "$file" =~ $allowlist ]] && continue
  if grep -InE "$forbidden" -- "$file" > "$hit_file" 2>/dev/null; then
    echo "licensing-grep: forbidden term in $file"
    sed 's/^/  /' "$hit_file"
    hits=1
  fi
done < <(git ls-files)

if [[ "$hits" -ne 0 ]]; then
  echo "licensing-grep: forbidden core-book content found, see NOTICE.md" >&2
  exit 1
fi

echo "licensing-grep: clean"
