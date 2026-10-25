---
name: video-edit
description: Edit and render videos with ffmpeg instead of CapCut — lyric videos (cover image + song + Korean/English lyric subtitles), vertical 9:16 Shorts/Reels, and travel vlogs (join clips with crossfades, background music, title text). Use whenever the user asks to make, edit, cut, subtitle, or export a video, including lyric videos for Suno songs.
---

# Video editing without CapCut

All rendering goes through `.claude/skills/video-edit/video.py` (ffmpeg + the Pretendard Korean font installed by the SessionStart hook). Save outputs under `generated-videos/` (git-ignored; this repository is public) and send the finished MP4 with `SendUserFile`. Run renders with a timeout of at least 600000 ms; a 3–4 minute 1080p song takes a few minutes.

## Lyric video (main use)

1. Lyrics text: follow step 1 of the `srt` skill to settle the Korean lyrics and a line-for-line English version, and get the user's OK. Save them as `{title}_ko.txt` / `{title}_en.txt`, one lyric line per line.
2. Lyrics timing: instead of that skill's Whisper matching, force-align with Demucs + stable-ts (subtitle text stays exactly the lyrics):
   ```bash
   python3 .claude/skills/video-edit/align_lyrics.py --audio song.wav \
     --lyrics song_ko.txt --translation song_en.txt \
     --out generated-videos/song_ko.srt --out-translation generated-videos/song_en.srt
   ```
   `--model medium` is the default (`small` is faster, `large-v3` more accurate). The first run downloads the model; a 3–4 minute song takes several minutes on CPU. Warn the user if it prints a segment/line count mismatch, and spot-check a few cue times.
3. Cover: if the user has none, make one with the `gpt-image` skill (square, no text).
4. Render:
   ```bash
   python3 .claude/skills/video-edit/video.py lyric \
     --image cover.png --audio song.wav \
     --srt song_ko.srt --srt2 song_en.srt \
     --out generated-videos/song.mp4
   ```
   - `--size 1080x1920` for a vertical Shorts/Reels version (default `1920x1080` for YouTube).
   - `--zoom` adds a slow zoom-in (slower to render).
   - Omit `--srt2` for Korean-only lyrics.

## Shorts / Reels (9:16)

```bash
python3 .claude/skills/video-edit/video.py shorts --input clip.mp4 \
  --start 00:00:10 --end 00:00:40 [--fit blur|crop] [--srt subs.srt] \
  [--music bgm.mp3 --music-volume 0.3] --out generated-videos/short.mp4
```
`blur` (default) keeps the whole frame over a blurred background; `crop` fills the screen by cutting the sides. SRT times are in the source video's timeline.

## Travel vlog

```bash
python3 .claude/skills/video-edit/video.py vlog --clips a.mp4 b.mp4 c.mp4 \
  [--music bgm.mp3 --music-volume 0.35 --clip-volume 1.0] \
  [--title "이집트 레고 여행"] [--transition 0.5] [--size 1920x1080] \
  --out generated-videos/vlog.mp4
```
Clips are joined in order with crossfades; clips of a different shape sit over a blurred copy of themselves. To trim clips first, cut them with `ffmpeg -ss START -to END -i in.mp4 -c:v libx264 -c:a aac part.mp4`.

## Other tools (installed by the SessionStart hook)

- **Instrumental / vocals only (Demucs):** `demucs --two-stems=vocals -n htdemucs -o generated-videos/stems song.wav` → `vocals.wav` and `no_vocals.wav` (MR / karaoke). Roughly 1–2× the song length on CPU.
- **Cut silent parts (auto-editor):** `auto-editor talk.mp4 --margin 0.2s --no-open -o generated-videos/talk_cut.mp4` — good for vlog talking clips.
- **Split long footage into scenes (PySceneDetect):** `scenedetect -i trip.mp4 -o generated-videos/scenes detect-content list-scenes split-video` — then pick scenes for Shorts or the vlog.

## Notes

- The font has no emoji; emoji are dropped from titles, so don't put them in subtitles either.
- For anything these commands don't cover (speed changes, color grading, overlays), call ffmpeg directly.
- After rendering, pull a frame (`ffmpeg -ss 5 -i out.mp4 -frames:v 1 frame.png`) and look at it before sending.
