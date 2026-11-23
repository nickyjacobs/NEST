"""Build assets/quickstart.gif: the first steps in VS Code, as five real screens with a caption.

  python3 assets/start/src/compose.py gif-1 gif-2 gif-3 gif-4 gif-5   # the frames, from raw screenshots
  python3 assets/quickstart-src/slides.py                            # the GIF

Each slide is one composed screenshot from assets/start/ (see assets/start/src/README.md for how
those are made and why the raw screenshots are not in the repository) with a bar underneath:
the number of the step, one sentence, and a dot per slide. Chrome renders the slides headless,
ffmpeg joins them. Needs Google Chrome and ffmpeg.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FRAMES = ROOT / "assets" / "start"
OUT = ROOT / "assets" / "quickstart.gif"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTH, HEIGHT, BAR = 1400, 960, 80
SLIDES = [  # frame, caption, how the frame fills the slide, seconds
    ("gif-1.png", "Add Claude Code to VS Code", "cover", 3.2),
    ("gif-2.png", "Open the NEST folder", "cover", 3.2),
    ("gif-3.png", "Trust the folder", "contain", 3.2),
    ("gif-4.png", "Trust it in Claude Code too", "contain", 3.2),
    ("gif-5.png", "Type one sentence. The setup takes it from there.", "cover", 4.5),
]
PAGE = """<!doctype html><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#0d0d10}}
.f{{width:{w}px;height:{h}px;position:relative;overflow:hidden;font:600 30px/1 -apple-system,"Segoe UI",Roboto,sans-serif}}
.p{{position:absolute;left:0;top:0;width:{w}px;height:{ph}px;background:#0d0d10 url('{img}') center {pos}/{fit} no-repeat}}
.b{{position:absolute;left:0;bottom:0;width:{w}px;height:{bar}px;background:#17171d;border-top:1px solid #2a2a34;display:flex;align-items:center;gap:18px;padding:0 28px;color:#fff}}
.n{{width:44px;height:44px;border-radius:50%;background:#f5a55a;color:#17110a;display:grid;place-items:center;font-weight:800;font-size:24px}}
.d{{margin-left:auto;display:flex;gap:8px}}.d i{{width:10px;height:10px;border-radius:50%;background:#3a3a46}}.d i.on{{background:#f5a55a}}
</style><div class="f"><div class="p"></div><div class="b"><span class="n">{n}</span><span>{text}</span><span class="d">{dots}</span></div></div>"""


def main() -> None:
    missing = [name for name, *_ in SLIDES if not (FRAMES / name).is_file()]
    if missing:
        raise SystemExit("frames missing, run compose.py first: " + ", ".join(missing))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        lines = []
        for i, (frame, text, fit, seconds) in enumerate(SLIDES):
            dots = "".join('<i class="on"></i>' if j == i else "<i></i>" for j in range(len(SLIDES)))
            page = work / f"s{i}.html"
            page.write_text(PAGE.format(w=WIDTH, h=HEIGHT, ph=HEIGHT - BAR, bar=BAR, img=(FRAMES / frame).as_uri(),
                                        pos="top" if fit == "cover" else "center", fit=fit, n=i + 1, text=text, dots=dots),
                            encoding="utf-8")
            subprocess.run([CHROME, "--headless=new", "--force-device-scale-factor=1", f"--window-size={WIDTH},{HEIGHT}",
                            f"--screenshot={work / f's{i}.png'}", page.as_uri()], check=True, capture_output=True)
            lines += [f"file 's{i}.png'", f"duration {seconds}"]
        lines.append(f"file 's{len(SLIDES) - 1}.png'")
        (work / "list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        scale = "fps=5,scale=1200:-1:flags=lanczos"
        ff = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt"]
        subprocess.run([*ff, "-vf", f"{scale},palettegen=max_colors=96", "palette.png"], check=True, cwd=work)
        subprocess.run([*ff, "-i", "palette.png", "-lavfi", f"{scale}[x];[x][1:v]paletteuse=dither=none", str(OUT)],
                       check=True, cwd=work)
    print(f"written: {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
