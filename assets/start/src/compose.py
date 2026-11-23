"""Put numbered callouts on a real screenshot and write the picture the guide shows.

  python3 compose.py            every shot in shots.json
  python3 compose.py 2-extensions

shots.json names, per picture: the raw screenshot in ../raw/, how much to cut off the top (the
menu bar of the operating system) or a crop box [left, top, width, height], areas to cover (a list of recent folders is private: it is
covered with an empty stretch of the same screenshot), text to write over a covered
area (a path with a user name in it becomes an example path), a ring around what matters, and the
callouts. Coordinates are in pixels of the raw screenshot. Chrome renders the result headless.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CSS = """
*{box-sizing:border-box} html,body{margin:0;background:transparent}
.s{position:relative;overflow:hidden;font:600 22px/1.25 -apple-system,"Segoe UI",Roboto,sans-serif}
.s img{position:absolute;left:0}
.patch{position:absolute;background-repeat:no-repeat}
.label{position:absolute;color:#e6e6e6;font-weight:400;white-space:nowrap;line-height:1}
.ring{position:absolute;border:4px solid #f5a55a;border-radius:12px;box-shadow:0 0 0 6px rgba(245,165,90,.22)}
.n{position:absolute;width:46px;height:46px;border-radius:50%;background:#f5a55a;color:#17110a;font-weight:800;font-size:24px;display:grid;place-items:center;box-shadow:0 0 0 6px rgba(245,165,90,.28),0 4px 14px rgba(0,0,0,.5)}
.tip{position:absolute;background:#f5a55a;color:#17110a;padding:9px 16px;border-radius:11px;white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,.5)}
"""


def build(name: str, shot: dict) -> None:
    width, height = shot["width"], shot["height"]
    left, top, out_w, out_h = shot.get("crop") or [0, shot.get("top", 0), width, height - shot.get("top", 0)]
    raw = (HERE.parent / "raw" / shot["raw"]).as_uri()
    parts = [f'<img src="{raw}" style="top:{-top}px;left:{-left}px" width="{width}">']
    for x, y, w, h, from_x, from_y in shot.get("cover", []):
        parts.append(
            f'<div class="patch" style="left:{x - left}px;top:{y - top}px;width:{w}px;height:{h}px;'
            f'background-image:url({raw});background-size:{width}px auto;'
            f'background-position:{-from_x}px {-from_y}px"></div>'
        )
    for x, y, text, size in shot.get("labels", []):
        parts.append(f'<div class="label" style="left:{x - left}px;top:{y - top}px;font-size:{size}px">{text}</div>')
    for x, y, w, h in shot.get("rings", []):
        parts.append(f'<div class="ring" style="left:{x - left}px;top:{y - top}px;width:{w}px;height:{h}px"></div>')
    for number, x, y, text, tip_x, tip_y in shot.get("callouts", []):
        parts.append(f'<div class="n" style="left:{x - left - 23}px;top:{y - top - 23}px">{number}</div>')
        if text:
            parts.append(f'<div class="tip" style="left:{tip_x - left}px;top:{tip_y - top}px">{text}</div>')
    page = HERE / f"{name}.built.html"
    page.write_text(
        f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>'
        f'<div class="s" style="width:{out_w}px;height:{out_h}px">{"".join(parts)}</div>',
        encoding="utf-8",
    )
    out = HERE.parent / f"{name}.png"
    subprocess.run(
        [CHROME, "--headless=new", "--force-device-scale-factor=1", "--default-background-color=00000000",
         f"--window-size={out_w},{out_h}", f"--screenshot={out}", page.as_uri()],
        check=True, capture_output=True,
    )
    page.unlink()
    print(f"written: {out.name}")


def main() -> None:
    shots = json.loads((HERE / "shots.json").read_text(encoding="utf-8"))
    for name in sys.argv[1:] or shots:
        build(name, shots[name])


if __name__ == "__main__":
    main()
