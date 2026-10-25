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

# ffmpeg for the video-edit skill
if ! command -v ffmpeg >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq ffmpeg
fi

# Korean font for video subtitles
font_dir="$HOME/.local/share/fonts/video-edit"
if [ ! -s "$font_dir/Pretendard-Bold.otf" ]; then
  mkdir -p "$font_dir"
  curl -fsSL -o "$font_dir/Pretendard-Bold.otf" \
    "https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/public/static/Pretendard-Bold.otf"
  fc-cache -f >/dev/null 2>&1 || true
fi
