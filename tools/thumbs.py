"""Write 480x270 copies of every image in <assets> to <assets>/thumbs/, same file names.

Usage: tools\\venv\\Scripts\\python.exe tools\\thumbs.py <assets folder>
deploy.ps1 runs this on the build copy, so src/ never gets a thumbs folder.
"""
import os
import sys
from PIL import Image, ImageOps

EXTS = (".jpg", ".jpeg", ".png", ".webp")


def main(assets):
    out = os.path.join(assets, "thumbs")
    os.makedirs(out, exist_ok=True)
    for name in sorted(os.listdir(assets)):
        if not name.lower().endswith(EXTS):
            continue
        im = ImageOps.fit(Image.open(os.path.join(assets, name)).convert("RGB"), (480, 270), Image.LANCZOS)
        # keep the format the file name says, so the TV never has to sniff it
        fmt = "WEBP" if name.lower().endswith(".webp") else "JPEG"
        im.save(os.path.join(out, name), fmt, quality=78)
        print("thumb", name)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
