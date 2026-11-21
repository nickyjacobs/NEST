# The GIFs

Both GIFs are a mock of VS Code with the integrated terminal, animated by `render(t)` in a scene
file and captured frame by frame.

| GIF | Scene | Re-render when |
|---|---|---|
| `assets/quickstart.gif` | `scene.html` | the first lines of `SETUP.md` or its line count change |
| `assets/nest-update.gif` | `scene-update.html` | the wording of `/nest-update` changes |

`scene.html` holds the look. `build.py` copies its `<style>` block into `scene-update.html`, so a
change to the styling means rendering both.

```bash
cd assets/quickstart-src
npm i -D playwright && npx playwright install chromium

render() {  # render <scene> <gif>
  python3 build.py "$1"                           # writes <scene>.built.html
  rm -rf frames
  node capture.mjs "$PWD" 12 "" "$1"              # frames/0000.png ... at 12 fps
  ffmpeg -y -framerate 12 -i frames/%04d.png -vf "palettegen=max_colors=128:stats_mode=diff" palette.png
  ffmpeg -y -framerate 12 -i frames/%04d.png -i palette.png -lavfi "paletteuse=dither=none:diff_mode=rectangle" "../$2"
}
render scene quickstart.gif
render scene-update nest-update.gif
```

To look at a few moments first, pass the seconds as the third argument:
`node capture.mjs "$PWD" 12 "3,12,24" scene-update` writes `frames/still-3.png` and so on.

The answer text in the quick start is the setup's real first reply from a trial run. The update
scene shows a fictional workspace and a fictional release 1.1.0.
