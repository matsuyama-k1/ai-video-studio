#!/usr/bin/env python3
"""Setup helper for the AI video tools. Plain-language output for non-technical users.

  doctor.py check                 what is ready / missing (never prints key values)
  doctor.py install-ffmpeg        download ffmpeg + ffprobe (checksum-verified) into the app's own folder
  doctor.py workspace             create .env.local / .gitignore / projects/ in the current folder
  doctor.py keys                  test each API key in .env.local with a free request
  doctor.py demo                  make a sample storyboard project ("sample") that works without any API key

Standard library only. Run from the folder that will hold the projects.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
sys.path.insert(0, str(SKILLS / "video-prompt" / "scripts"))
import toolpath  # noqa: E402  (adds the app's ffmpeg folder to PATH)
from seedance import load_env  # noqa: E402

BIN = toolpath.BIN
KEYS = {
    "OPENAI_API_KEY": "画像の生成・範囲修正(ChatGPT Images / GPT Image)",
    "KLING_API_KEY": "動画の生成(Kling)",
    "ARK_API_KEY": "動画の生成(Seedance)と画像の生成(Seedream)",
    "GEMINI_API_KEY": "動画の生成(Gemini Omni Flash)と画像の生成",
}
ENV_TEMPLATE = """# APIキーを書くファイルです。使うものだけ、= の右に貼り付けて保存してください。
# このファイルの中身は誰にも送らないでください。

# 画像の生成・範囲修正(ChatGPT Images / GPT Image) https://platform.openai.com/api-keys
OPENAI_API_KEY=

# 動画の生成(Kling) https://kling.ai/dev/api-key
KLING_API_KEY=

# 動画の生成(Seedance)・画像の生成(Seedream) https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey
ARK_API_KEY=

# 動画の生成(Gemini Omni Flash)・画像の生成 https://aistudio.google.com/apikey
GEMINI_API_KEY=
"""
GITIGNORE = """.env.local
outputs/
projects/*/scenes/*/renders/*.mp4
projects/*/scenes/*/renders/*.jpg
projects/*/storyboard/audio/
projects/*/storyboard/animatic.mp4
projects/*/storyboard/frames/_placeholder-*
"""


def sh(args, timeout=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def line(ok, name, detail, fix=""):
    mark = {True: "OK", False: "NG", None: "--"}[ok]
    print(f"[{mark}] {name}: {detail}" + (f"\n      → {fix}" if fix else ""))
    return ok


# ---------- check ----------

def cmd_check(a):
    results = {}
    mac = platform.system() == "Darwin"
    results["mac"] = line(mac, "パソコン", f"{platform.system()} {platform.mac_ver()[0]} ({platform.machine()})",
                          "" if mac else "このツールは Mac 専用です")
    py = sys.version_info >= (3, 9)
    results["python"] = line(py, "Python", sys.version.split()[0], "" if py else "Python 3.9 以上が必要です")
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        results[tool] = line(bool(path), tool, path or "見つかりません",
                             "" if path else "セットアップで自動インストールできます(doctor.py install-ffmpeg)")
    code, voices = sh(["say", "-v", "?"])
    kyoko = "Kyoko" in voices
    results["voice"] = line(kyoko, "日本語の読み上げ音声", "Kyoko あり" if kyoko else "見つかりません",
                            "" if kyoko else "システム設定 > アクセシビリティ > 読み上げコンテンツ > システムの声 で日本語の声を追加")
    codex = shutil.which("codex")
    if codex:
        code, out = sh(["codex", "login", "status"])
        logged = code == 0 and "Logged in" in out
        results["codex"] = line(logged if logged else None, "Codex(ChatGPTプランで画像生成・任意)",
                                "ログイン済み" if logged else "インストール済み・未ログイン",
                                "" if logged else "使う場合は、ターミナルで codex login")
    else:
        results["codex"] = line(None, "Codex(ChatGPTプランで画像生成・任意)", "未インストール(なくても使えます)")

    env = Path(".env.local")
    results["workspace"] = line(env.exists() and Path("projects").exists(), "作業フォルダ", str(Path.cwd()),
                                "" if env.exists() else "セットアップで作成します(doctor.py workspace)")
    load_env()
    for k, what in KEYS.items():
        has = bool(os.environ.get(k))
        results[k] = line(True if has else None, k, ("設定あり" if has else "未設定") + f" … {what}")
    print("\n" + json.dumps({k: v for k, v in results.items()}, ensure_ascii=False))


# ---------- ffmpeg ----------

def cmd_install_ffmpeg(a):
    arch = "arm64" if platform.machine() == "arm64" else "amd64"
    BIN.mkdir(parents=True, exist_ok=True)
    for tool in ("ffmpeg", "ffprobe"):
        url = f"https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/snapshot/{tool}.zip"
        ua = {"User-Agent": "Mozilla/5.0 (Macintosh) ai-video-setup"}   # the site rejects Python's default agent
        with urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=120) as r:
            final = r.geturl()
            data = r.read()
        with urllib.request.urlopen(urllib.request.Request(final + ".sha256", headers=ua), timeout=30) as r:
            expected = r.read().decode().split()[0]
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            sys.exit(f"{tool}: ダウンロードしたファイルの検証に失敗しました(チェックサム不一致)。中止します。")
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / f"{tool}.zip"
            z.write_bytes(data)
            with zipfile.ZipFile(z) as zf:
                zf.extract(tool, tmp)
            dest = BIN / tool
            shutil.move(str(Path(tmp) / tool), dest)
            dest.chmod(0o755)
        code, out = sh([str(dest), "-version"])
        if code:
            sys.exit(f"{tool} を起動できませんでした: {out[:300]}")
        print(f"{tool}: インストールしました({dest}) {out.splitlines()[0][:60]}")
    print(f"出どころ: ffmpeg.martin-riedl.de(署名済み・チェックサム確認済み)")


# ---------- workspace ----------

def cmd_workspace(a):
    made = []
    if not Path(".env.local").exists() or Path(".env.local").stat().st_size == 0:
        Path(".env.local").write_text(ENV_TEMPLATE)
        made.append(".env.local(APIキーを書くファイル)")
    gi = Path(".gitignore")
    if not gi.exists():
        gi.write_text(GITIGNORE)
        made.append(".gitignore")
    if not Path("projects").exists():
        Path("projects").mkdir()
        made.append("projects/(動画プロジェクトの置き場所)")
    print("作成しました: " + ", ".join(made) if made else "作業フォルダはすでに準備できています")
    print(f"場所: {Path.cwd()}")


# ---------- keys ----------

def probe(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(2000).decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode(errors="replace")
    except OSError as e:
        return None, str(e)


def cmd_keys(a):
    load_env()
    checks = {
        "OPENAI_API_KEY": lambda k: probe("https://api.openai.com/v1/models", {"Authorization": f"Bearer {k}"}),
        "GEMINI_API_KEY": lambda k: probe("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
                                          {"x-goog-api-key": k}),
        "ARK_API_KEY": lambda k: probe("https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks?page_size=1",
                                       {"Authorization": f"Bearer {k}"}),
        "KLING_API_KEY": lambda k: probe("https://api-singapore.klingai.com/tasks?task_ids=setup-check",
                                         {"Authorization": f"Bearer {k}"}),
    }
    for name, fn in checks.items():
        key = os.environ.get(name)
        if not key:
            line(None, name, f"未設定 … {KEYS[name]}")
            continue
        status, body = fn(key)
        if status is None:
            line(False, name, "通信できませんでした", "インターネット接続を確認してください")
        elif status in (401, 403) or (name == "KLING_API_KEY" and '"code":100' in body.replace(" ", "")):
            line(False, name, "キーが正しくないようです", "コピーし直して .env.local に貼り付けてください(前後の空白に注意)")
        elif status < 300 or (name == "KLING_API_KEY" and status < 500):
            line(True, name, "使えます")
        else:
            line(False, name, f"確認できませんでした(HTTP {status})", body[:160].replace("\n", " "))


# ---------- demo ----------

DEMO_CUTS = [
    ("c01", "s01-desk", 3, "山積みのレポートを前に、ため息をつく先生", "WS", "fixed shot", "静かなオフィスの環境音",
     "", "今日もレポートが山積みだ。"),
    ("c02", "s01-desk", 3, "パソコンでAIツールを開く", "MCU", "slow push-in", "キーボードの音",
     "", "そこで、新しい方法を試してみた。"),
    ("c03", "s02-talk", 4, "学生と笑顔で話す先生", "MS", "slow pan right", "明るいピアノ",
     "これなら、一人ひとりとちゃんと話せる。", ""),
]


def cmd_demo(a):
    sb = SKILLS / "storyboard" / "scripts" / "sb.py"
    if (Path("projects") / "sample").exists():
        print("サンプル(projects/sample)はすでにあります")
        return
    code, out = sh([sys.executable, str(sb), "init", "sample"], timeout=60)
    if code:
        sys.exit(out)
    p = Path("projects/sample/storyboard/cuts.json")
    data = json.loads(p.read_text())
    template = data["cuts"][0]
    data["project"].update(title="サンプル: AI添削で先生が楽になる", style_ja="やわらかい実写、自然光",
                           style_en="a soft, natural-light live-action look")
    cuts = []
    for cid, scene, dur, summary, shot, move, sound, line_, narration in DEMO_CUTS:
        c = json.loads(json.dumps(template))
        c.update(id=cid, scene=scene, duration=dur, summary_ja=summary, frame="", frame_prompt="",
                 refs=[], narration_ja=narration, notes_ja="")
        c.pop("ref_video", None)
        c["composition"]["shot"] = shot
        c["camera"]["move"] = move
        c["audio"]["ja"] = sound
        c["audio"]["dialogue"] = [{"speaker": "Teacher", "lang": "Japanese", "delivery": "", "line": line_}] if line_ else []
        cuts.append(c)
    data["cuts"] = cuts
    data["project"]["voices"] = {"Teacher": "Kyoko", "narrator": "Kyoko", "default": "Kyoko"}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print("サンプルを作りました: projects/sample(3カット・画像なし・APIキー不要)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("check", cmd_check), ("install-ffmpeg", cmd_install_ffmpeg), ("workspace", cmd_workspace),
                     ("keys", cmd_keys), ("demo", cmd_demo)]:
        sub.add_parser(name).set_defaults(f=fn)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
