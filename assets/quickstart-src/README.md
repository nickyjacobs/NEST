# The GIFs

| GIF | Made from | Make it again when |
|---|---|---|
| `assets/quickstart.gif` | five real screenshots of VS Code, with `slides.py` | VS Code or the Claude Code extension changes what a beginner sees in the first steps, or the first sentence changes |
| `assets/nest-update.gif` | `scene-update.html`, a drawn terminal animated frame by frame | the wording of `/nest-update` changes |

## The quick start

Five slides, each a real screen with a bar underneath: the number of the step, one sentence,
and a dot per slide. The screens are the same ones the getting-started guide shows.

```bash
python3 assets/start/src/compose.py gif-1 gif-2 gif-3 gif-4 gif-5   # the frames, from the raw screenshots
python3 assets/quickstart-src/slides.py                            # assets/quickstart.gif
```

The frames come from raw screenshots that are not in the repository (they can show private
folders); `assets/start/src/README.md` says how those are made and what is covered. Needs
Google Chrome and ffmpeg. The captions and the time per slide are at the top of `slides.py`.

## The update

`scene-update.html` is a mock of VS Code with the integrated terminal, animated by `render(t)`
and captured frame by frame. `scene.html` holds the look: `build.py` copies its `<style>` block
into `scene-update.html`. It shows a fictional workspace and a fictional release.

```bash
cd assets/quickstart-src
npm i -D playwright && npx playwright install chromium

python3 build.py scene-update                     # writes scene-update.built.html
rm -rf frames
node capture.mjs "$PWD" 12 "" scene-update        # frames/0000.png ... at 12 fps
ffmpeg -y -framerate 12 -i frames/%04d.png -vf "palettegen=max_colors=128:stats_mode=diff" palette.png
ffmpeg -y -framerate 12 -i frames/%04d.png -i palette.png -lavfi "paletteuse=dither=none:diff_mode=rectangle" ../nest-update.gif
```

To look at a few moments first, pass the seconds as the third argument:
`node capture.mjs "$PWD" 12 "3,12,24" scene-update` writes `frames/still-3.png` and so on.
