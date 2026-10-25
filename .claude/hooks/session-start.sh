#!/bin/bash
set -euo pipefail

# Only run in Claude Code cloud sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install the Codex CLI if it isn't already available
if ! command -v codex >/dev/null 2>&1; then
  npm install -g @openai/codex
fi
