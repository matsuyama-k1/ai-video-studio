"""Make the ffmpeg/ffprobe that the setup skill installs visible to every script.

The setup skill downloads them into the app's own folder (no Homebrew, no admin password),
so each entry script imports this module to put that folder at the front of PATH.
"""
import os
from pathlib import Path

BIN = Path.home() / "Library" / "Application Support" / "AI Video Studio" / "bin"
if str(BIN) not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = f"{BIN}{os.pathsep}{os.environ.get('PATH', '')}"


MISSING = "動画の部品(ffmpeg)が見つかりません。Claude に「/ai-video:setup」と話しかけて準備してください。"
