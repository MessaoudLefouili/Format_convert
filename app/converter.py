import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg", ".ts", ".3gp")

# name -> (kbps, channels)
PRESETS = {
    "Voix": (64, 1),
    "Standard": (128, 2),
    "Haute": (192, 2),
}

FORMATS = ("mp3", "m4a")

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_TIME_RE = re.compile(r"out_time_us=(\d+)")


def ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def unique_output(src: Path, out_dir: Path, fmt: str) -> Path:
    out = out_dir / f"{src.stem}.{fmt}"
    n = 1
    while out.exists():
        out = out_dir / f"{src.stem}_{n}.{fmt}"
        n += 1
    return out


def build_command(ffmpeg: str, src: Path, dst: Path, fmt: str, preset: str) -> list:
    kbps, channels = PRESETS[preset]
    cmd = [ffmpeg, "-y", "-hide_banner", "-nostdin", "-i", str(src), "-vn", "-map", "0:a:0",
           "-ac", str(channels)]
    if fmt == "mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", f"{kbps}k"]
    elif fmt == "m4a":
        cmd += ["-c:a", "aac", "-b:a", f"{kbps}k", "-movflags", "+faststart"]
    else:
        raise ValueError(f"Format non supporté: {fmt}")
    cmd += ["-progress", "pipe:1", "-nostats", str(dst)]
    return cmd


def parse_duration(line: str) -> Optional[float]:
    m = _DURATION_RE.search(line)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def parse_progress(line: str) -> Optional[float]:
    m = _TIME_RE.search(line)
    return int(m.group(1)) / 1_000_000 if m else None


class Cancelled(Exception):
    pass


class Converter:
    def __init__(self):
        self.ffmpeg = ffmpeg_path()
        self._proc: Optional[subprocess.Popen] = None
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def reset(self) -> None:
        self._cancel = False

    def _duration(self, src: Path) -> Optional[float]:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run([self.ffmpeg, "-hide_banner", "-i", str(src)], capture_output=True,
                           text=True, errors="replace", creationflags=flags)
        return parse_duration(r.stderr)

    def convert(self, src: Path, out_dir: Path, fmt: str, preset: str,
                on_progress: Callable[[float], None] = lambda p: None) -> Path:
        """Convertit un fichier. Retourne le chemin de sortie, lève RuntimeError ou Cancelled."""
        if self._cancel:
            raise Cancelled()
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = unique_output(src, out_dir, fmt)
        total = self._duration(src)
        cmd = build_command(self.ffmpeg, src, dst, fmt, preset)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, errors="replace", creationflags=flags)
        proc = self._proc
        try:
            for line in proc.stdout:
                t = parse_progress(line)
                if t is not None and total:
                    on_progress(min(t / total, 1.0))
            err = proc.stderr.read()
            proc.wait()
        finally:
            self._proc = None
        if self._cancel:
            _remove(dst)
            raise Cancelled()
        if proc.returncode != 0:
            _remove(dst)
            tail = err.strip().splitlines()[-1] if err.strip() else "erreur ffmpeg"
            raise RuntimeError(tail)
        on_progress(1.0)
        return dst


def _remove(path: Path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def is_video(path: str) -> bool:
    return path.lower().endswith(VIDEO_EXTS)
