"""Build a scene into <scene>.built.html, ready for capture.mjs.

  python3 build.py                 scene.html: filled with the current head and line count of SETUP.md
  python3 build.py scene-update    scene-update.html: gets the <style> block of scene.html, so both
                                   GIFs share one look
"""
import json
import re
import sys
from pathlib import Path

here = Path(__file__).parent
name = sys.argv[1].removesuffix(".html") if len(sys.argv) > 1 else "scene"
setup = (here.parent.parent / "SETUP.md").read_text(encoding="utf-8")
base = (here / "scene.html").read_text(encoding="utf-8")
scene = (here / f"{name}.html").read_text(encoding="utf-8")
scene = scene.replace("__SHARED_STYLE__", re.search(r"<style>.*?</style>", base, re.S).group(0))
scene = scene.replace("__SETUP_HEAD__", json.dumps(setup.split("\n")[:10]))
scene = scene.replace("__SETUP_LINES__", str(len(setup.splitlines())))
(here / f"{name}.built.html").write_text(scene, encoding="utf-8")
