#!/bin/bash
# Generate an image with Codex (ChatGPT login, no API credits) and save it.
# Usage: generate.sh "<prompt>" <output.png>
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 \"<prompt>\" <output.png>" >&2
  exit 1
fi

prompt="$1"
out="$(realpath -m "$2")"
mkdir -p "$(dirname "$out")"

if ! command -v codex >/dev/null 2>&1; then
  npm install -g @openai/codex >/dev/null
fi

if ! codex login status 2>&1 | grep -q "ChatGPT"; then
  echo "NOT_LOGGED_IN: run 'codex login --device-auth' and give the user the code" >&2
  exit 2
fi

workdir="$(mktemp -d)"
codex exec --skip-git-repo-check --sandbox workspace-write -C "$workdir" \
  "Use your built-in image generation tool to create exactly one image. Prompt: ${prompt}
Save the result as image.png in the current directory. Do not do anything else." >"$workdir/codex.log" 2>&1 || true

if [ ! -s "$workdir/image.png" ]; then
  echo "Image generation failed. Codex output:" >&2
  tail -20 "$workdir/codex.log" >&2
  exit 3
fi

mv "$workdir/image.png" "$out"
rm -rf "$workdir"
echo "$out"
