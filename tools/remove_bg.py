"""Remove the white background from icon images and save them as square PNGs.

Usage:  tools\\venv\\Scripts\\python.exe tools\\remove_bg.py <input> <output.png> [<input> <output.png> ...]

Uses withoutbg's local open-weights model (downloaded on first run, no API key).
Each result is trimmed to the visible pixels, centred on a transparent square
and saved at 512x512, which is plenty for a TV tile.
"""
import sys
from PIL import Image
from withoutbg import WithoutBG

SIZE = 512
PAD = 0.04  # breathing room around the art, as a fraction of the side


def square(img):
    bbox = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    side = int(max(w, h) * (1 + 2 * PAD))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main(args):
    if not args or len(args) % 2:
        sys.exit(__doc__)
    model = WithoutBG.open_weights()
    for src, dst in zip(args[0::2], args[1::2]):
        out = model.remove_background(src)
        if not isinstance(out, Image.Image):
            out = Image.open(out)
        square(out.convert("RGBA")).save(dst, optimize=True)
        print(f"ok  {src} -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
