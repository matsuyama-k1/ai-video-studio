"""Storyboard page: one HTML page (an Artifact on claude.ai, or a local file) built from cuts.json.

build(project_dir, data) -> (html, files)
  html   page content without <html>/<head>/<body> (the Artifact publisher adds the skeleton)
  files  {published path: local file} for the frames and the animatic MP4 the page references
wrap(html) -> a standalone document for opening locally when there is no Artifact tool.
"""
import html as h
from pathlib import Path

SHOT_JA = {"EWS": "超ロング", "WS": "ロング", "FS": "フル", "MWS": "ミドルロング", "MS": "ミディアム",
           "MCU": "バスト", "CU": "アップ", "ECU": "超アップ", "OTS": "肩越し", "POV": "主観", "INSERT": "インサート"}

STYLE = """
<style>
/* Light table: graphite panels on a cool grey board; slate-yellow marks timecode and the current cut. */
:root{
  --board:#e9ecef; --panel:#ffffff; --ink:#15181d; --muted:#5b6370; --rule:#d5d9df; --slate:#d9a400; --slate-ink:#1a1500;
  --hatch:#dfe3e8; --scene-a:#c9d6ea; --scene-b:#e8d6c4; --scene-c:#cfe3d3; --scene-d:#e0d1e8;
  --sans:"Zen Kaku Gothic New","Hiragino Sans","Noto Sans JP",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --board:#111317; --panel:#1b1e24; --ink:#e8eaee; --muted:#9299a5; --rule:#2c3038; --slate:#f0c02b; --slate-ink:#1a1500;
  --hatch:#23272e; --scene-a:#2b3a52; --scene-b:#4a3a2b; --scene-c:#2b4632; --scene-d:#3f2f4a; color-scheme:dark}}
:root[data-theme="dark"]{
  --board:#111317; --panel:#1b1e24; --ink:#e8eaee; --muted:#9299a5; --rule:#2c3038; --slate:#f0c02b; --slate-ink:#1a1500;
  --hatch:#23272e; --scene-a:#2b3a52; --scene-b:#4a3a2b; --scene-c:#2b4632; --scene-d:#3f2f4a; color-scheme:dark}
body{background:var(--board);color:var(--ink);font:15px/1.6 var(--sans)}
.wrap{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:24px 48px;display:grid;gap:28px}
header{display:grid;gap:6px}
h1{font-size:clamp(22px,4vw,30px);line-height:1.25;margin:0;font-weight:700;text-wrap:balance}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;color:var(--muted);font-size:13px}
.meta b{color:var(--ink);font-family:var(--mono);font-weight:500}
.reel{display:grid;gap:8px}
.reel video{width:100%;max-width:760px;border-radius:6px;background:#000;display:block}
.note{font-size:12px;color:var(--muted)}
.strip{display:flex;height:34px;border-radius:5px;overflow:hidden;border:1px solid var(--rule)}
.strip a{display:flex;align-items:center;justify-content:center;min-width:0;font:500 11px/1 var(--mono);color:var(--ink);
  text-decoration:none;border-right:1px solid var(--panel);white-space:nowrap;overflow:hidden}
.strip a:last-child{border-right:0}
.strip a:focus-visible{outline:2px solid var(--slate);outline-offset:-2px}
section{display:grid;gap:12px}
h2{margin:0;font-size:14px;font-weight:700;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
h2 span{font:500 12px var(--mono);color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,290px),1fr));gap:16px}
.cut{background:var(--panel);border:1px solid var(--rule);border-radius:6px;overflow:hidden;display:flex;flex-direction:column;min-width:0}
.frame{position:relative;aspect-ratio:var(--ar);max-width:100%;
  background:repeating-linear-gradient(45deg,var(--hatch) 0 2px,transparent 2px 11px)}
.frame img{width:100%;height:100%;object-fit:cover;display:block}
.frame .empty{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted);font-size:13px}
.tc{position:absolute;left:8px;top:8px;background:var(--slate);color:var(--slate-ink);font:500 11px/1 var(--mono);
  padding:5px 7px;border-radius:3px;letter-spacing:.02em}
.body{padding:12px 14px 14px;display:grid;gap:10px;min-width:0}
.sum{font-weight:700;line-height:1.45}
.chips{display:flex;flex-wrap:wrap;gap:4px}
.chips span{font-size:11.5px;border:1px solid var(--rule);border-radius:3px;padding:1px 6px;color:var(--muted)}
dl{margin:0;display:grid;grid-template-columns:4.2em 1fr;gap:3px 10px;font-size:13px}
dt{color:var(--muted);font-size:12px;letter-spacing:.04em}
dd{margin:0;min-width:0;overflow-wrap:anywhere}
.line{font-weight:500}
details{border-top:1px solid var(--rule);padding:8px 14px;font-size:12px;color:var(--muted)}
summary{cursor:pointer}
details pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0 0;font:12px/1.5 var(--mono);color:var(--ink)}
@media (prefers-reduced-motion:no-preference){.strip a{transition:filter .15s}.strip a:hover{filter:brightness(.92)}}
</style>
"""

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500'
         '&family=Zen+Kaku+Gothic+New:wght@500;700&display=swap">')


def esc(s):
    return h.escape(str(s if s is not None else ""))


def tc(sec):
    m, s = divmod(max(0.0, float(sec)), 60)
    return f"{int(m):02d}:{s:04.1f}"


def g(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d or ""


def sound(c):
    a = c.get("audio") or {}
    parts = [f"<span class='line'>{esc(d.get('speaker'))}「{esc(d.get('line'))}」</span>"
             for d in a.get("dialogue") or [] if d.get("line")]
    if c.get("narration_ja"):
        parts.append(f"<span class='line'>ナレーション「{esc(c['narration_ja'])}」</span>")
    if a.get("ja"):
        parts.append(esc(a["ja"]))
    return "<br>".join(parts)


def card(c, start, files, project_dir, english):
    comp, cam, tempo = c.get("composition") or {}, c.get("camera") or {}, c.get("tempo") or {}
    dur = float(c.get("duration") or 0)
    img = "<div class='empty'>画像なし</div>"
    if c.get("frame") and (project_dir / c["frame"]).exists():
        pub = "frames/" + Path(c["frame"]).name
        files[pub] = str(project_dir / c["frame"])
        img = f"<img src='{esc(pub)}' alt='{esc(c.get('summary_ja'))}' loading='lazy'>"
    chips = [SHOT_JA.get(comp.get("shot", ""), comp.get("shot")), comp.get("angle"), comp.get("lens"),
             cam.get("move"), tempo.get("pace")]
    rows = [("構図", comp.get("ja")), ("カメラ", cam.get("ja")), ("光", g(c, "lighting", "ja")),
            ("色", g(c, "color", "ja")), ("動き", g(c, "action", "ja")), ("場所", g(c, "setting", "ja")),
            ("テンポ", tempo.get("ja")), ("つなぎ", tempo.get("transition_out")), ("メモ", c.get("notes_ja"))]
    dl = "".join(f"<dt>{k}</dt><dd>{esc(v)}</dd>" for k, v in rows if v)
    snd = sound(c)
    if snd:
        dl += f"<dt>音</dt><dd>{snd}</dd>"
    return (f"<article class='cut' id='{esc(c['id'])}'>"
            f"<div class='frame'>{img}<div class='tc'>{esc(c['id'].upper())} {tc(start)}–{tc(start + dur)}</div></div>"
            f"<div class='body'><div class='sum'>{esc(c.get('summary_ja'))}</div>"
            f"<div class='chips'>{''.join(f'<span>{esc(x)}</span>' for x in chips if x)}</div><dl>{dl}</dl></div>"
            f"<details><summary>AIへの指示(英語)</summary><pre>{esc(english)}</pre></details></article>")


def build(project_dir, data, english_of):
    project_dir = Path(project_dir)
    proj, cuts = data["project"], data["cuts"]
    w, hgt = (proj.get("aspect") or "16:9").split(":")
    total = sum(float(c.get("duration") or 0) for c in cuts)
    files = {}

    scenes, starts, t = [], {}, 0.0
    for c in cuts:
        starts[c["id"]] = t
        t += float(c.get("duration") or 0)
        if not scenes or scenes[-1][0] != c.get("scene"):
            scenes.append((c.get("scene"), []))
        scenes[-1][1].append(c)

    tones = ["--scene-a", "--scene-b", "--scene-c", "--scene-d"]
    strip = "".join(
        f"<a href='#{esc(c['id'])}' style='flex:{max(float(c.get('duration') or 0), .1)};background:var({tones[i % 4]})' "
        f"title='{esc(c['id'])} {esc(c.get('summary_ja'))}'>{esc(c['id'])}</a>"
        for i, (_, group) in enumerate(scenes) for c in group)

    reel = ""
    mp4 = project_dir / "storyboard" / "animatic.mp4"
    if mp4.exists():
        files["animatic.mp4"] = str(mp4)
        stale = (project_dir / "storyboard" / "cuts.json").stat().st_mtime > mp4.stat().st_mtime + 1
        reel = ("<div class='reel'><video src='animatic.mp4' controls playsinline preload='metadata'></video>"
                f"<div class='note'>アニマティック(仮の音声つき){'・絵コンテを直す前の版です' if stale else ''}</div></div>")

    sections = "".join(
        f"<section><h2>{esc(name)}<span>{tc(starts[group[0]['id']])}–"
        f"{tc(starts[group[-1]['id']] + float(group[-1].get('duration') or 0))} · {len(group)}カット</span></h2>"
        f"<div class='grid'>{''.join(card(c, starts[c['id']], files, project_dir, english_of(c)) for c in group)}</div></section>"
        for name, group in scenes)

    title = proj.get("title") or project_dir.name
    page = (f"<title>{esc(title)} 絵コンテ</title>\n{FONTS}\n{STYLE}"
            f"<div class='wrap' style='--ar:{w}/{hgt}'><header><h1>{esc(title)}</h1>"
            f"<div class='meta'><span><b>{len(cuts)}</b> カット</span><span>全長 <b>{tc(total)}</b></span>"
            f"<span>画面 <b>{esc(proj.get('aspect'))}</b></span><span>{esc(proj.get('style_ja'))}</span></div></header>"
            f"{reel}<nav class='strip' aria-label='カットの時間配分'>{strip}</nav>{sections}</div>")
    return page, files


def wrap(page):
    return ("<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'></head>"
            f"<body style='margin:0'>{page}</body></html>")
