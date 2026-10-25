#!/usr/bin/env python3
"""Video editing with ffmpeg, no CapCut needed.

Subcommands:
  lyric   cover image + song + SRT lyrics (Korean, optional English) -> MP4
  shorts  cut a clip into a vertical 9:16 short, optional subtitles
  vlog    join clips with crossfades and background music
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

FONT_DIR = os.path.expanduser("~/.local/share/fonts/video-edit")
FONT_NAME = "Pretendard"


def run(cmd):
    print("+ " + " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    duration = float(info["format"]["duration"])
    has_audio = any(s["codec_type"] == "audio" for s in info.get("streams", []))
    return duration, has_audio


def parse_size(size):
    w, h = size.lower().split("x")
    return int(w), int(h)


# ---------- subtitles ----------

def parse_srt(path):
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            m = re.match(r"(\S+)\s*-->\s*(\S+)", line)
            if m:
                cues.append((to_sec(m.group(1)), to_sec(m.group(2)),
                             "\\N".join(l.strip() for l in lines[i + 1:] if l.strip())))
                break
    return cues


def to_sec(ts):
    h, m, s = ts.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def ass_time(sec):
    cs = int(round(sec * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(path, width, height, tracks, offset=0.0):
    """tracks: list of (cues, style) where style is 'main' or 'sub'."""
    main_size = round(height * (0.055 if width >= height else 0.040))
    sub_size = round(main_size * 0.65)
    margin_v = round(height * (0.08 if width >= height else 0.18))
    sub_margin = margin_v
    main_margin = margin_v + (round(sub_size * 1.6) if len(tracks) > 1 else 0)
    style = ("Style: {name},{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
             "-1,0,0,0,100,100,0,0,1,{outline},2,2,{ml},{ml},{mv},1")
    ml = round(width * 0.06)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 0", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style.format(name="main", font=FONT_NAME, size=main_size,
                     outline=max(2, main_size // 14), ml=ml, mv=main_margin),
        style.format(name="sub", font=FONT_NAME, size=sub_size,
                     outline=max(2, sub_size // 14), ml=ml, mv=sub_margin),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cues, name in tracks:
        for start, end, text in cues:
            start, end = start - offset, end - offset
            if end <= 0:
                continue
            fade = "{\\fad(200,200)}"
            lines.append(f"Dialogue: 0,{ass_time(max(0, start))},{ass_time(end)},{name},,0,0,0,,"
                         f"{fade}{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def subtitle_filter(ass_path):
    esc = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"ass='{esc}':fontsdir='{FONT_DIR}'"


def build_tracks(srt, srt2):
    tracks = [(parse_srt(srt), "main")] if srt else []
    if srt2:
        tracks.append((parse_srt(srt2), "sub"))
    return tracks


def encode_args(crf):
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]


# ---------- lyric video ----------

def cmd_lyric(a):
    w, h = parse_size(a.size)
    duration, _ = probe(a.audio)
    fps = 30
    tmp = tempfile.mkdtemp()
    # Blurred cover fills the frame; the sharp cover sits centered on top.
    cover = round(min(w, h) * 0.62)
    cover_y = "(H-h)/2-H*0.08" if a.srt else "(H-h)/2"
    # Compose the background once as a still frame so each video frame only adds lyrics.
    base = os.path.join(tmp, "base.png")
    run(["ffmpeg", "-v", "error", "-y", "-i", a.image, "-filter_complex",
         f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
         f"gblur=sigma=40,eq=brightness=-0.15[bg];"
         f"[b]scale={cover}:{cover}:force_original_aspect_ratio=decrease[fg];"
         f"[bg][fg]overlay=(W-w)/2:{cover_y},setsar=1", "-frames:v", "1", base])
    bg = "[0:v]setsar=1"
    if a.zoom:
        frames = int(duration * fps) + fps
        bg += (f",scale={w * 2}:{h * 2},zoompan=z='min(1+on/{frames}*0.08,1.08)':"
               f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={fps}")
    tracks = build_tracks(a.srt, a.srt2)
    if tracks:
        ass = os.path.join(tmp, "lyrics.ass")
        write_ass(ass, w, h, tracks)
        bg += "," + subtitle_filter(ass)
    bg += f",fps={fps},format=yuv420p[v]"
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", base, "-i", a.audio,
         "-filter_complex", bg, "-map", "[v]", "-map", "1:a", "-t", f"{duration:.3f}",
         *encode_args(a.crf), "-tune", "stillimage", a.out])


# ---------- shorts ----------

def cmd_shorts(a):
    w, h = 1080, 1920
    duration, has_audio = probe(a.input)
    start = to_sec(a.start) if a.start else 0.0
    end = to_sec(a.end) if a.end else duration
    tmp = tempfile.mkdtemp()
    if a.fit == "crop":
        vf = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    else:
        vf = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h},gblur=sigma=30,eq=brightness=-0.1[bg];"
              f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    tracks = build_tracks(a.srt, a.srt2)
    if tracks:
        ass = os.path.join(tmp, "subs.ass")
        write_ass(ass, w, h, tracks, offset=start)
        vf += "," + subtitle_filter(ass)
    vf += ",fps=30,format=yuv420p[v]"
    cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", a.input]
    maps = ["-map", "[v]"]
    if a.music:
        cmd += ["-stream_loop", "-1", "-i", a.music]
        vf += mix_audio(has_audio, end - start, a.music_volume)
        maps += ["-map", "[aout]"]
    elif has_audio:
        maps += ["-map", "0:a"]
    run(cmd + ["-filter_complex", vf, *maps, "-t", f"{end - start:.3f}",
               *encode_args(a.crf), a.out])


def mix_audio(has_orig, length, music_volume, orig_label="0:a", music_label="1:a"):
    fade_out = max(0.0, length - 2)
    music = (f";[{music_label}]volume={music_volume},afade=t=in:d=1,"
             f"afade=t=out:st={fade_out:.3f}:d=2,atrim=0:{length:.3f}[m]")
    if has_orig:
        return music + f";[{orig_label}][m]amix=inputs=2:duration=first:normalize=0[aout]"
    return music + ";[m]anull[aout]"


# ---------- vlog ----------

def cmd_vlog(a):
    w, h = parse_size(a.size)
    fps = 30
    xf = a.transition
    infos = [probe(c) for c in a.clips]
    cmd = ["ffmpeg", "-y"]
    for c in a.clips:
        cmd += ["-i", c]
    parts = []
    for i, (dur, has_audio) in enumerate(infos):
        # Clips with a different shape sit over a blurred copy of themselves instead of black bars.
        parts.append(f"[{i}:v]split[s{i}a][s{i}b];[s{i}a]scale={w}:{h}:force_original_aspect_ratio=increase,"
                     f"crop={w}:{h},gblur=sigma=30,eq=brightness=-0.1[bg{i}];"
                     f"[s{i}b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg{i}];"
                     f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps},format=yuv420p[v{i}]")
        if has_audio:
            parts.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[a{i}]")
    vlast, alast, total = "v0", "a0", infos[0][0]
    for i in range(1, len(a.clips)):
        offset = total - xf
        parts.append(f"[{vlast}][v{i}]xfade=transition=fade:duration={xf}:offset={offset:.3f}[vx{i}]")
        parts.append(f"[{alast}][a{i}]acrossfade=d={xf}[ax{i}]")
        vlast, alast = f"vx{i}", f"ax{i}"
        total = offset + infos[i][0]
    if a.title:
        # The font has no emoji glyphs, so drop them rather than draw empty boxes.
        txt = "".join(ch for ch in a.title
                      if not (0x2600 <= ord(ch) <= 0x27BF or ord(ch) >= 0x1F000
                              or ord(ch) in (0x200D, 0xFE0F))).strip()
        txt = txt.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
        font = os.path.join(FONT_DIR, "Pretendard-Bold.otf")
        parts.append(f"[{vlast}]drawtext=fontfile='{font}':text='{txt}':fontcolor=white:"
                     f"fontsize={round(h * 0.08)}:borderw=4:bordercolor=black@0.6:"
                     f"x=(w-text_w)/2:y=(h-text_h)/2:"
                     f"alpha='if(lt(t,0.5),t/0.5,if(lt(t,3),1,if(lt(t,4),4-t,0)))'[vt]")
        vlast = "vt"
    tmp = tempfile.mkdtemp()
    tracks = build_tracks(a.srt, None)
    if tracks:
        ass = os.path.join(tmp, "subs.ass")
        write_ass(ass, w, h, tracks)
        parts.append(f"[{vlast}]{subtitle_filter(ass)}[vs]")
        vlast = "vs"
    graph = ";".join(parts)
    if a.music:
        cmd += ["-stream_loop", "-1", "-i", a.music]
        n = len(a.clips)
        graph += f";[{alast}]volume={a.clip_volume}[ao]"
        graph += mix_audio(True, total, a.music_volume, orig_label="ao", music_label=f"{n}:a")
        alast = "aout"
    run(cmd + ["-filter_complex", graph, "-map", f"[{vlast}]", "-map", f"[{alast}]",
               "-t", f"{total:.3f}", *encode_args(a.crf), a.out])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    l = sub.add_parser("lyric", help="cover image + song + lyrics -> MP4")
    l.add_argument("--image", required=True)
    l.add_argument("--audio", required=True)
    l.add_argument("--srt", help="main lyrics SRT (e.g. Korean)")
    l.add_argument("--srt2", help="second, smaller lyrics SRT (e.g. English)")
    l.add_argument("--size", default="1920x1080", help="1920x1080 (YouTube) or 1080x1920 (Shorts)")
    l.add_argument("--zoom", action="store_true", help="slow zoom-in over the song")
    l.add_argument("--crf", type=int, default=20)
    l.add_argument("--out", required=True)
    l.set_defaults(func=cmd_lyric)

    s = sub.add_parser("shorts", help="vertical 9:16 short from a video")
    s.add_argument("--input", required=True)
    s.add_argument("--start", help="HH:MM:SS(.ms) start time")
    s.add_argument("--end", help="HH:MM:SS(.ms) end time")
    s.add_argument("--fit", choices=["blur", "crop"], default="blur",
                   help="blur: whole frame over blurred background; crop: fill by cropping sides")
    s.add_argument("--srt")
    s.add_argument("--srt2")
    s.add_argument("--music")
    s.add_argument("--music-volume", type=float, default=0.3)
    s.add_argument("--crf", type=int, default=20)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_shorts)

    v = sub.add_parser("vlog", help="join clips with crossfades and music")
    v.add_argument("--clips", nargs="+", required=True)
    v.add_argument("--music")
    v.add_argument("--music-volume", type=float, default=0.35)
    v.add_argument("--clip-volume", type=float, default=1.0)
    v.add_argument("--transition", type=float, default=0.5, help="crossfade seconds")
    v.add_argument("--title", help="title text shown for the first few seconds")
    v.add_argument("--srt")
    v.add_argument("--size", default="1920x1080")
    v.add_argument("--crf", type=int, default=20)
    v.add_argument("--out", required=True)
    v.set_defaults(func=cmd_vlog)

    a = p.parse_args()
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    a.func(a)
    print(os.path.abspath(a.out))


if __name__ == "__main__":
    main()
