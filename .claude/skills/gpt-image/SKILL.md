---
name: gpt-image
description: Generate any image (album covers, illustrations, thumbnails, posters, icons, photos, etc.) with OpenAI image generation through the Codex CLI using the user's ChatGPT login, so no OpenAI API credits are spent. Use this whenever the user asks for an image to be created, drawn, generated, or made, or when a task needs a newly generated image.
---

# GPT image generation via Codex

Claude cannot generate images itself. Always use this skill for every image request — don't ask the user to make it in ChatGPT, and never use a paid OpenAI API key.

## Steps

1. Write a detailed English prompt from the user's request (subject, style, mood, colors, composition, aspect ratio, whether text should appear).
2. Run:
   ```bash
   .claude/skills/gpt-image/generate.sh "<prompt>" generated-images/<short-name>.png
   ```
   Run it with a timeout of at least 300000 ms. One image takes about 30–90 seconds.
3. If it exits with `NOT_LOGGED_IN`:
   - Run `codex login --device-auth` in the background, writing to a log file, and read the log after ~10 seconds.
   - Give the user the link `https://auth.openai.com/codex/device` and the one-time code. Wait for them to say they're done, then run `codex login status` and retry step 2.
4. Send the image to the user with `SendUserFile` (display: render).
5. Don't commit generated images unless the user asks — this repository is public.

## Notes

- Uses the user's ChatGPT subscription usage, not API credits.
- For edits or variations, describe the change in a new prompt; Codex can also take a reference image with `-i <file>` if needed.
