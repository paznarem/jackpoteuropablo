#!/usr/bin/env bash
# Auto-commit + push: se ejecuta al terminar cada turno (hook Stop).
# Si hay cambios en el working tree, los sube al repositorio.
set -euo pipefail

REPO="/workspaces/jackpoteuropablo"
cd "$REPO" || exit 0

# Nada que subir -> salir en silencio.
if [ -z "$(git status --porcelain)" ]; then
  exit 0
fi

git add -A

# Por si acaso quedara vacío tras el add (p. ej. solo ignore).
if git diff --cached --quiet; then
  exit 0
fi

TS="$(date '+%Y-%m-%d %H:%M:%S')"
git commit -q -m "Auto-commit: $TS"

if git push -q 2>/tmp/claude-autopush.err; then
  printf '{"systemMessage": "✅ Cambios subidos al repositorio (%s)"}\n' "$TS"
else
  ERR="$(tr '\n' ' ' < /tmp/claude-autopush.err | sed 's/"/\\"/g')"
  printf '{"systemMessage": "⚠️ Commit hecho pero el push falló: %s"}\n' "$ERR"
fi
