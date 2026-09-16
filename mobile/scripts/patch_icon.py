#!/usr/bin/env python3
from pathlib import Path
from PIL import Image

MOBILE = Path(__file__).resolve().parents[1]
REPO = MOBILE.parent
ANDROID_RES = MOBILE / "android" / "app" / "src" / "main" / "res"
SOURCE = REPO / "icon-512.png"

SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    for density, size in SIZES.items():
        target_dir = ANDROID_RES / f"mipmap-{density}"
        target_dir.mkdir(parents=True, exist_ok=True)
        icon = source.resize((size, size), Image.Resampling.LANCZOS)
        icon.save(target_dir / "ic_launcher.png", optimize=True)
        icon.save(target_dir / "ic_launcher_round.png", optimize=True)
    adaptive = ANDROID_RES / "mipmap-anydpi-v26"
    if adaptive.exists():
        for xml in adaptive.glob("*.xml"):
            xml.unlink()
    print("Patched Android launcher icons")

if __name__ == "__main__":
    main()
