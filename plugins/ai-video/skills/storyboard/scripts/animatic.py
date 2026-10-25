"""Animatic: play the storyboard as timed stills with temporary voice (macOS `say`), edit it in
the browser, export an MP4, and assemble a one-page contact sheet. Used by sb.py.

cuts.json stays the single source of truth: browser edits are written back to it.
"""
import datetime as dt
import hashlib
import http.server
import json
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
from pathlib import Path

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
SIZES = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1080, 1080), "4:3": (960, 720),
         "3:4": (720, 960), "21:9": (1680, 720)}
FPS = 24


def run(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        import toolpath
        raise RuntimeError(toolpath.MISSING if args[0] in ("ffmpeg", "ffprobe") else f"{args[0]} が見つかりません")
    if r.returncode:
        raise RuntimeError(f"{args[0]} failed: {r.stderr.strip()[-400:]}")
    return r


def media_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return round(float(r.stdout.strip() or 0), 2)


def size_of(data):
    return SIZES.get(data["project"].get("aspect") or "16:9", (1280, 720))


def lines_of(cut):
    """[(speaker, text)] spoken in this cut: dialogue lines, then narration."""
    out = [(d.get("speaker") or "", d.get("line") or "") for d in (cut.get("audio") or {}).get("dialogue") or []]
    if cut.get("narration_ja"):
        out.append(("narrator", cut["narration_ja"]))
    return [(s, t) for s, t in out if t.strip()]


def subtitle_of(cut):
    return " / ".join(t for _, t in lines_of(cut))


# ---------- temporary voice ----------

def voice_for(data, speaker):
    voices = data["project"].get("voices") or {}
    return voices.get(speaker) or voices.get("default") or "Kyoko"


def tts_cut(project_dir, data, cut, rate=None):
    """Synthesize the cut's lines with `say` into storyboard/audio/<id>.m4a. Cached by text+voice."""
    lines = lines_of(cut)
    if not lines:
        cut.pop("tts", None)
        return None
    rate = rate or data["project"].get("voice_rate") or 180
    spec = json.dumps([(voice_for(data, s), t) for s, t in lines] + [rate], ensure_ascii=False)
    digest = hashlib.sha1(spec.encode()).hexdigest()[:10]
    out = project_dir / "storyboard" / "audio" / f"{cut['id']}.m4a"
    if (cut.get("tts") or {}).get("hash") == digest and out.exists():
        return cut["tts"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (speaker, text) in enumerate(lines):
            aiff = Path(tmp) / f"{i}.aiff"
            run(["say", "-v", voice_for(data, speaker), "-r", str(rate), "-o", str(aiff), text])
            parts.append(aiff)
        inputs = sum((["-i", str(p)] for p in parts), [])
        # 0.2 s of silence between lines
        chain = "".join(f"[{i}:a]apad=pad_dur=0.2[a{i}];" for i in range(len(parts)))
        chain += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
        run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", chain, "-map", "[out]",
             "-c:a", "aac", "-b:a", "128k", str(out)])
    cut["tts"] = {"file": str(out.relative_to(project_dir)), "duration": media_duration(out), "hash": digest}
    return cut["tts"]


def tts_all(project_dir, data, rate=None):
    report = []
    for c in data["cuts"]:
        t = tts_cut(project_dir, data, c, rate)
        if t:
            over = t["duration"] > float(c.get("duration") or 0)
            report.append(f"{c['id']}: {t['duration']}s / cut {c.get('duration')}s" + ("  ! longer than the cut" if over else ""))
    return report


# ---------- stills ----------

def placeholder(project_dir, data, cut):
    """Gray card with the cut id and summary, for cuts that have no frame yet."""
    w, h = size_of(data)
    out = project_dir / "storyboard" / "frames" / f"_placeholder-{cut['id']}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(f"{cut['id']}  {cut.get('summary_ja', '')}")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x3a3f47:s={w}x{h}",
         "-frames:v", "1", "-vf", f"drawtext=fontfile='{FONT}':textfile='{f.name}':fontsize={h // 18}:"
         "fontcolor=white@0.85:x=(w-tw)/2:y=(h-th)/2", str(out)])
    Path(f.name).unlink()
    return out


def still_of(project_dir, data, cut):
    if cut.get("frame") and (project_dir / cut["frame"]).exists():
        return project_dir / cut["frame"]
    return placeholder(project_dir, data, cut)


def motion_of(cut):
    """Rough camera move for the preview, read from camera.move."""
    m = ((cut.get("camera") or {}).get("move") or "").lower()
    if any(k in m for k in ("pull", "zoom out", "dolly out", "dolly-out", "pull-out", "pull back")):
        return "out"
    if any(k in m for k in ("push", "dolly-in", "dolly in", "zoom in", "zoom-in", "move in")):
        return "in"
    if "left" in m and any(k in m for k in ("pan", "track", "truck", "slide")):
        return "left"
    if "right" in m and any(k in m for k in ("pan", "track", "truck", "slide")):
        return "right"
    if "crane up" in m or "tilt up" in m or "rise" in m:
        return "up"
    if "crane down" in m or "tilt down" in m:
        return "down"
    return "none"


# ---------- MP4 export ----------

def export(project_dir, data, out=None):
    w, h = size_of(data)
    out = Path(out or project_dir / "storyboard" / "animatic.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        segs = []
        for i, c in enumerate(data["cuts"]):
            d = float(c.get("duration") or 3)
            n = max(1, int(round(d * FPS)))
            img = still_of(project_dir, data, c)
            mv = motion_of(c)
            z = {"in": f"1+0.12*on/{n}", "out": f"1.12-0.12*on/{n}"}.get(mv, "1.08")
            x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*on/{n}"}.get(mv, "iw/2-(iw/zoom/2)")
            y = {"up": f"(ih-ih/zoom)*(1-on/{n})", "down": f"(ih-ih/zoom)*on/{n}"}.get(mv, "ih/2-(ih/zoom/2)")
            vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                  f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={FPS}")
            sub = subtitle_of(c)
            if sub:
                tf = Path(tmp) / f"sub{i}.txt"
                tf.write_text(sub)
                vf += (f",drawtext=fontfile='{FONT}':textfile='{tf}':fontsize={h // 24}:fontcolor=white:"
                       f"box=1:boxcolor=black@0.55:boxborderw=12:x=(w-tw)/2:y=h-th-{h // 12}")
            label = Path(tmp) / f"lab{i}.txt"
            label.write_text(f"{c['id']}  {d:g}s")
            vf += (f",drawtext=fontfile='{FONT}':textfile='{label}':fontsize={h // 36}:fontcolor=white@0.8:"
                   f"box=1:boxcolor=black@0.4:boxborderw=6:x=16:y=16")
            audio = project_dir / (c.get("tts") or {}).get("file", "__none__")
            ain = ["-i", str(audio)] if audio.exists() else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            seg = Path(tmp) / f"seg{i:03d}.mp4"
            run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(img), *ain,
                 "-filter_complex", f"[0:v]{vf}[v];[1:a]aresample=44100,apad[a]", "-map", "[v]", "-map", "[a]",
                 "-t", f"{d:.3f}", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                 "-c:a", "aac", "-ar", "44100", "-ac", "2", str(seg)])
            segs.append(seg)
        lst = Path(tmp) / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


# ---------- contact sheet ----------

def contact_sheet(project_dir, data, cols=3, out=None):
    """All cut stills on one page with id, seconds and summary drawn by the program (not the image model)."""
    w, h = size_of(data)
    tw = 640
    th = int(tw * h / w)
    out = Path(out or project_dir / "storyboard" / "sheet.png")
    with tempfile.TemporaryDirectory() as tmp:
        tiles = []
        for i, c in enumerate(data["cuts"]):
            cap = Path(tmp) / f"cap{i}.txt"
            cap.write_text(f"{c['id']}  {float(c.get('duration') or 0):g}s  {c.get('summary_ja', '')}"[:44])
            tile = Path(tmp) / f"t{i:03d}.png"
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(still_of(project_dir, data, c)), "-vf",
                 f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},pad={tw}:{th + 44}:0:0:white,"
                 f"drawtext=fontfile='{FONT}':textfile='{cap}':fontsize=22:fontcolor=black:x=10:y={th + 11}",
                 "-frames:v", "1", str(tile)])
            tiles.append(tile)
        rows = (len(tiles) + cols - 1) // cols
        for k in range(len(tiles), rows * cols):     # blank tiles to fill the last row
            blank = Path(tmp) / f"t{k:03d}.png"
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=white:s={tw}x{th + 44}",
                 "-frames:v", "1", str(blank)])
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(Path(tmp) / "t%03d.png"), "-vf",
             f"tile={cols}x{rows}:padding=12:margin=12:color=white", "-frames:v", "1", str(out)])
    return out


# ---------- browser player / editor ----------

EDITABLE = ("duration", "summary_ja", "notes_ja", "narration_ja")


def merge_edits(data, edits):
    """Apply browser edits; returns human-readable change notes for the log."""
    by_id = {c["id"]: c for c in data["cuts"]}
    notes = []
    for e in edits:
        c = by_id.get(e.get("id"))
        if not c:
            continue
        for k in EDITABLE:
            if k in e and e[k] != c.get(k, "" if k != "duration" else None):
                old = c.get(k)
                c[k] = float(e[k]) if k == "duration" else e[k]
                notes.append(f"{c['id']} {k}: {old} → {c[k]}")
        lines = e.get("lines")
        dialogue = (c.get("audio") or {}).get("dialogue") or []
        if isinstance(lines, list):
            for d, new in zip(dialogue, lines):
                if new != d.get("line"):
                    notes.append(f"{c['id']} セリフ: {d.get('line')} → {new}")
                    d["line"] = new
    return notes


def append_log(project_dir, target, change, reason):
    log = project_dir / "storyboard" / "log.md"
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with log.open("a") as f:
        f.write(f"| {now} | {target} | {change.replace('|', '/')} | {reason} |\n")


def serve(project_dir, load, save, port=8765, open_browser=True):
    project_dir = Path(project_dir).resolve()
    templates = Path(__file__).resolve().parent.parent / "templates"
    pages = {"/": "animatic.html", "/index.html": "animatic.html", "/frame": "frame.html"}
    lock = threading.Lock()

    def assets():
        """Images that can be used as references: refs/ (not reference-video analysis) and every cut's picture."""
        out = []
        refs = project_dir / "refs"
        for f in sorted(refs.rglob("*")) if refs.exists() else []:
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and "video" not in f.relative_to(refs).parts[:1]:
                out.append({"file": str(f.relative_to(project_dir)), "label": f.name})
        for c in load()["cuts"]:
            if c.get("frame"):
                out.append({"file": c["frame"], "label": f"{c['id']} 現在"})
        return out

    def frame_op(cut_id, fn):
        """Run a slow image call on a copy, then merge only the picture fields into a fresh load (other edits survive)."""
        import frames
        data = load()
        cut = next((c for c in data["cuts"] if c["id"] == cut_id), None)
        if not cut:
            raise RuntimeError(f"cut {cut_id} not found")
        result = fn(frames, data, cut)
        with lock:
            fresh = load()
            target = next(c for c in fresh["cuts"] if c["id"] == cut_id)
            for k in ("frame", "frame_prompt", "frame_history", "refs"):
                if k in cut:
                    target[k] = cut[k]
            save(fresh)
        last = (cut.get("frame_history") or [{}])[-1]
        append_log(project_dir, cut_id, f"画像 {last.get('mode')}: {result}", last.get("prompt") or last.get("source") or "")
        return result

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(project_dir), **kw)

        def log_message(self, *a):
            pass

        def send_json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path in pages:
                body = (templates / pages[path]).read_text().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/assets":
                self.send_json({"assets": assets()})
            elif path == "/api/cuts":
                data = load()
                for c in data["cuts"]:
                    c["_motion"] = motion_of(c)
                self.send_json(data)
            else:
                super().do_GET()

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            try:
                if u.path == "/api/cuts":
                    data = load()
                    notes = merge_edits(data, body.get("cuts") or [])
                    if notes:
                        save(data)
                        for n in notes:
                            append_log(project_dir, n.split(" ")[0], n, "ブラウザで編集")
                    self.send_json({"ok": True, "changes": notes})
                elif u.path == "/api/tts":
                    cut_id = urllib.parse.parse_qs(u.query).get("cut", [""])[0]
                    data = load()
                    targets = [c for c in data["cuts"] if not cut_id or c["id"] == cut_id]
                    for c in targets:
                        tts_cut(project_dir, data, c)
                    save(data)
                    self.send_json({"ok": True, "tts": {c["id"]: c.get("tts") for c in targets}})
                elif u.path == "/api/frame/generate":
                    def gen(fr, d, c):
                        if body.get("refs") is not None:
                            c["refs"] = body["refs"]          # chosen references become the cut's refs
                        return fr.generate(project_dir, d, c, body.get("provider") or "openai",
                                           body.get("prompt"), c.get("refs"), body.get("quality"))
                    f = frame_op(body["cut"], gen)
                    self.send_json({"ok": True, "frame": f})
                elif u.path == "/api/frame/edit":
                    f = frame_op(body["cut"], lambda fr, d, c: fr.edit(
                        project_dir, d, c, body.get("provider") or "openai", body["prompt"],
                        fr.decode_data_url(body.get("mask")), body.get("refs") or [], body.get("quality")))
                    self.send_json({"ok": True, "frame": f})
                elif u.path == "/api/frame/use":
                    f = frame_op(body["cut"], lambda fr, d, c: fr.use(project_dir, c, body["file"]))
                    self.send_json({"ok": True, "frame": f})
                else:
                    self.send_json({"error": "not found"}, 404)
            except Exception as e:  # report to the page instead of dropping the connection
                self.send_json({"error": str(e)}, 500)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"animatic: {url}  (Ctrl+C to stop)", flush=True)
    if open_browser and shutil.which("open"):
        subprocess.Popen(["open", url])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
