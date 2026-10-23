#!/usr/bin/env python3
"""Deixa os assets do Kurumi Home o mais leves possivel, sem mudar o layout.

- Wallpapers: WebP 1920x1080 (o app desenha em 1920x1080; 4K so gasta RAM).
  Se existir um original em originals/<nome>.png|jpg, ele e usado como fonte.
- Icones: WebP 320x320 com alfa (e o tamanho em que aparecem no bloco).
- Guarda uma copia dos arquivos antigos em tools/backups/assets-<data>/.

Uso:
    tools\\venv\\Scripts\\python.exe tools\\optimize_assets.py
Depois, ajuste os caminhos no src/config.json se algum arquivo mudou de extensao.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import time

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src" / "assets"
ORIGINALS = ROOT / "originals"
BACKUPS = ROOT / "tools" / "backups"
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def backup(path: pathlib.Path, dest: pathlib.Path) -> None:
    target = dest / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def original_for(stem: str) -> pathlib.Path | None:
    want = stem.replace(" ", "").lower()
    for p in ORIGINALS.glob("*"):
        if p.suffix.lower() in EXTS and p.stem.replace(" ", "").lower() == want:
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument("--icon", type=int, default=320)
    args = parser.parse_args()

    dest = BACKUPS / f"assets-{time.strftime('%Y%m%d-%H%M%S')}"
    before = after = 0

    for path in sorted(p for p in ASSETS.glob("wallpaper*") if p.suffix.lower() in EXTS):
        before += path.stat().st_size
        backup(path, dest)
        source = original_for(path.stem) or path
        with Image.open(source) as im:
            im = ImageOps.fit(im.convert("RGB"), (args.width, args.height), Image.LANCZOS)
            out = path.with_suffix(".webp")
            im.save(out, "WEBP", quality=args.quality, method=6)
        if out != path:
            path.unlink()
        after += out.stat().st_size
        print(f"{out.name}: {out.stat().st_size // 1024} KB (fonte: {source.name})")

    for path in sorted(p for p in (ASSETS / "icons").glob("*") if p.suffix.lower() in EXTS):
        before += path.stat().st_size
        backup(path, dest)
        with Image.open(path) as im:
            im = im.convert("RGBA")
            if max(im.size) > args.icon:
                im = im.resize((args.icon, args.icon), Image.LANCZOS)
            out = path.with_suffix(".webp")
            im.save(out, "WEBP", quality=88, alpha_quality=90, method=6)
        if out != path:
            path.unlink()
        after += out.stat().st_size
        print(f"{out.name}: {out.stat().st_size // 1024} KB")

    print(f"\nAntes: {before / 1024:.0f} KB")
    print(f"Depois: {after / 1024:.0f} KB")
    print(f"Backup: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
