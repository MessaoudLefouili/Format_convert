"""Usage: python -m app.cli sortie_dir mp3|m4a Preset fichier1 [fichier2 ...]"""
import sys
from pathlib import Path

from app.converter import Converter


def main(argv):
    out_dir, fmt, preset, *files = argv
    conv = Converter()
    for f in files:
        dst = conv.convert(Path(f), Path(out_dir), fmt, preset,
                           lambda p: print(f"\r{Path(f).name}: {p:4.0%}", end="", flush=True))
        print(f"\n-> {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
