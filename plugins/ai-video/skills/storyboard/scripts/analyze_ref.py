#!/usr/bin/env python3
"""Break a reference video into cuts so Claude can read composition, camera, lighting, tempo and audio.

  analyze_ref.py <video> --out <dir> [--threshold 0.3]

Writes into <dir>:
  analysis.json      duration, fps, size, cuts (start/end/length/volume), tempo stats, silences
  overview.jpg       one mid frame per cut, numbered, in a grid  -> read this first
  cut-NN.jpg         start | middle | end of each cut           -> read these to judge camera movement
  waveform.png       audio waveform of the whole clip

Needs ffmpeg / ffprobe. Standard library only.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "video-prompt" / "scripts"))
import toolpath  # noqa: E402,F401  (ffmpeg installed by the setup skill)


def sh(args):
    return subprocess.run(args, capture_output=True, text=True)


def probe(video):
    r = sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)])
    if r.returncode:
        sys.exit(r.stderr)
    info = json.loads(r.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or "0/1").split("/")
    return {
        "duration": float(info["format"]["duration"]),
        "fps": round(float(num) / float(den), 2) if float(den) else None,
        "width": v["width"], "height": v["height"],
        "has_audio": any(s["codec_type"] == "audio" for s in info["streams"]),
    }


def detect_cuts(video, threshold, duration):
    r = sh(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
            f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    bounds = [0.0] + [t for t in times if 0.3 < t < duration - 0.3] + [duration]
    cuts, start = [], bounds[0]
    for end in bounds[1:]:
        if end - start >= 0.3:          # merge flashes shorter than 0.3 s into the next cut
            cuts.append((start, end))
            start = end
    if cuts and cuts[-1][1] < duration:
        cuts[-1] = (cuts[-1][0], duration)
    return cuts


def grab(video, t, dest, width=480):
    sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
        "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)])
    return dest.exists()


def label(src, dest, text):
    """Burn a label into the top-left corner; falls back to a plain copy if drawtext is unavailable."""
    r = sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
            f"drawbox=x=0:y=0:w=150:h=34:color=black@0.6:t=fill,"
            f"drawtext=text='{text}':x=8:y=7:fontsize=20:fontcolor=white", str(dest)])
    if r.returncode or not dest.exists():
        sh(["cp", str(src), str(dest)])


def hstack(frames, dest):
    inputs = sum((["-i", str(f)] for f in frames), [])
    sh(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
        f"hstack=inputs={len(frames)}", "-q:v", "3", str(dest)])


def grid(frames, dest, cols=4):
    pattern = dest.parent / "_ov_%03d.jpg"
    for i, f in enumerate(frames):
        sh(["cp", str(f), str(dest.parent / f"_ov_{i:03d}.jpg")])
    rows = (len(frames) + cols - 1) // cols
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pattern), "-vf",
        f"tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1", "-q:v", "3", str(dest)])
    for f in dest.parent.glob("_ov_*.jpg"):
        f.unlink()


def mean_volume(video, start, end):
    r = sh(["ffmpeg", "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(video),
            "-vn", "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def silences(video):
    r = sh(["ffmpeg", "-hide_banner", "-i", str(video), "-vn", "-af",
            "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [{"start": round(s, 2), "end": round(e, 2)} for s, e in zip(starts, ends)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold", type=float, default=0.3, help="scene-change sensitivity (lower = more cuts)")
    a = ap.parse_args()

    video, out = Path(a.video), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = probe(video)
    cuts = detect_cuts(video, a.threshold, meta["duration"])
    if len(cuts) > 60:
        print(f"warning: {len(cuts)} cuts detected; try a higher --threshold", file=sys.stderr)

    rows, mids = [], []
    for i, (s, e) in enumerate(cuts, 1):
        pts = [s + min(0.1, (e - s) / 4), (s + e) / 2, e - min(0.1, (e - s) / 4)]
        frames = []
        for j, t in enumerate(pts):
            f = out / f"_c{i:02d}_{j}.jpg"
            if grab(video, t, f):
                frames.append(f)
        sheet = out / f"cut-{i:02d}.jpg"
        if frames:
            hstack(frames, sheet)
            mid = out / f"_mid{i:02d}.jpg"
            label(frames[len(frames) // 2], mid, f"{i:02d}  {e - s:.1f}s")
            mids.append(mid)
        for f in frames:
            f.unlink()
        rows.append({
            "n": i, "start": round(s, 2), "end": round(e, 2), "length": round(e - s, 2),
            "sheet": sheet.name if sheet.exists() else None,
            "mean_volume_db": mean_volume(video, s, e) if meta["has_audio"] else None,
        })

    if mids:
        grid(mids, out / "overview.jpg")
        for f in mids:
            f.unlink()
    if meta["has_audio"]:
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-filter_complex",
            "showwavespic=s=1600x200:colors=0x4a90d9", "-frames:v", "1", str(out / "waveform.png")])

    lengths = [r["length"] for r in rows]
    result = {
        "source": str(video), **meta,
        "cut_count": len(rows),
        "avg_shot_length": round(sum(lengths) / len(lengths), 2) if lengths else None,
        "cuts_per_minute": round(len(rows) / meta["duration"] * 60, 1) if meta["duration"] else None,
        "shortest": min(lengths, default=None), "longest": max(lengths, default=None),
        "silences": silences(video) if meta["has_audio"] else [],
        "cuts": rows,
    }
    (out / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ("cuts", "silences")}, ensure_ascii=False, indent=2))
    print(f"read: {out / 'overview.jpg'} then cut-NN.jpg")


if __name__ == "__main__":
    main()
