#!/bin/sh
# Poistka pred commitom: zabráni commitnúť rozbitý kód.
#   - compileall → chytí SyntaxError (napr. zlú úvodzovku v reťazci)
#   - pytest     → chytí rozbitú logiku / importy
#
# Inštalácia hooku (stačí raz):
#   cp scripts/precommit_check.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# Núdzové preskočenie (len výnimočne):
#   git commit --no-verify
set -e
cd "$(git rev-parse --show-toplevel)"

# Nájdi python z venv (Windows aj Linux), inak systémový.
PY=".venv/Scripts/python"
[ -x "$PY" ] || PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

echo "[pre-commit] compileall (kontrola syntaxe)…"
"$PY" -m compileall -q src tests

echo "[pre-commit] pytest…"
"$PY" -m pytest -q

echo "[pre-commit] OK"
