#!/usr/bin/env python3
"""Time known lyrics to a song and write an SRT, one cue per lyric line.

Separates the vocals with Demucs first (unless --no-separate), then force-aligns
the given lyrics with stable-ts, so the subtitle text is exactly the lyrics file.

Usage:
  align_lyrics.py --audio song.wav --lyrics song_ko.txt --out song_ko.srt
  align_lyrics.py ... --lang ko --model medium --translation song_en.txt --out-translation song_en.srt
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def read_lines(path):
    return [l.strip() for l in open(path, encoding="utf-8-sig") if l.strip()]


def srt_time(sec):
    ms = int(round(max(0.0, sec) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(path, cues):
    with open(path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(cues, 1):
            f.write(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n\n")


def separate_vocals(audio, workdir):
    run = ["demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", workdir, audio]
    print("+ " + " ".join(run), file=sys.stderr)
    subprocess.run(run, check=True)
    name = os.path.splitext(os.path.basename(audio))[0]
    return os.path.join(workdir, "htdemucs", name, "vocals.wav")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--lyrics", required=True, help="text file, one lyric line per line")
    p.add_argument("--out", required=True)
    p.add_argument("--lang", default="ko")
    p.add_argument("--model", default="medium", help="whisper model: small, medium, large-v3")
    p.add_argument("--no-separate", action="store_true", help="skip Demucs vocal separation")
    p.add_argument("--translation", help="second lyrics file with the same number of lines")
    p.add_argument("--out-translation")
    p.add_argument("--max-hold", type=float, default=1.5,
                   help="max seconds a line stays on screen after it is sung")
    a = p.parse_args()

    import stable_whisper

    lines = read_lines(a.lyrics)
    workdir = tempfile.mkdtemp()
    audio = a.audio if a.no_separate else separate_vocals(a.audio, workdir)

    model = stable_whisper.load_model(a.model)
    result = model.align(audio, "\n".join(lines), language=a.lang, original_split=True)
    segments = [s for s in result.segments if s.text.strip()]
    if len(segments) != len(lines):
        print(f"warning: {len(segments)} aligned segments for {len(lines)} lyric lines",
              file=sys.stderr)

    cues = []
    for i, line in enumerate(lines):
        if i >= len(segments):
            break
        seg = segments[i]
        nxt = segments[i + 1].start if i + 1 < len(segments) else seg.end + a.max_hold
        end = min(max(seg.end, seg.start + 0.8) + a.max_hold, nxt)
        cues.append((seg.start, end, line))
    write_srt(a.out, cues)
    print(os.path.abspath(a.out))

    if a.translation:
        tr = read_lines(a.translation)
        if len(tr) != len(lines):
            sys.exit(f"translation has {len(tr)} lines but lyrics have {len(lines)}")
        out_tr = a.out_translation or os.path.splitext(a.out)[0] + "_tr.srt"
        write_srt(out_tr, [(s, e, tr[i]) for i, (s, e, _) in enumerate(cues)])
        print(os.path.abspath(out_tr))

    shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
