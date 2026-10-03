import shutil
import subprocess
from pathlib import Path

import pytest

from app.converter import (Converter, build_command, ffmpeg_path, is_video, parse_duration,
                           parse_progress, unique_output)


def test_parse_duration():
    assert parse_duration("  Duration: 00:01:02.50, start: 0") == 62.5
    assert parse_duration("nothing") is None


def test_parse_progress():
    assert parse_progress("out_time_us=1500000") == 1.5
    assert parse_progress("progress=continue") is None


def test_unique_output(tmp_path):
    src = Path("a/video.mp4")
    assert unique_output(src, tmp_path, "mp3") == tmp_path / "video.mp3"
    (tmp_path / "video.mp3").touch()
    assert unique_output(src, tmp_path, "mp3") == tmp_path / "video_1.mp3"


def test_build_command():
    c = build_command("ff", Path("in.mp4"), Path("out.m4a"), "m4a", "Voix")
    assert "aac" in c and "64k" in c and c[c.index("-ac") + 1] == "1"
    c = build_command("ff", Path("in.mp4"), Path("out.mp3"), "mp3", "Haute")
    assert "libmp3lame" in c and "192k" in c
    with pytest.raises(ValueError):
        build_command("ff", Path("i"), Path("o"), "ogg", "Voix")


def test_is_video():
    assert is_video("X.MKV") and not is_video("a.txt")


@pytest.fixture
def sample(tmp_path):
    ff = ffmpeg_path()
    out = tmp_path / "sample.mp4"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=d=2:s=64x64:r=10", "-f", "lavfi",
                    "-i", "sine=d=2", "-shortest", str(out)], check=True, capture_output=True)
    return out


@pytest.mark.parametrize("fmt", ["mp3", "m4a"])
def test_convert(sample, tmp_path, fmt):
    seen = []
    dst = Converter().convert(sample, tmp_path / "out", fmt, "Voix", seen.append)
    assert dst.exists() and dst.suffix == f".{fmt}" and dst.stat().st_size > 0
    assert seen[-1] == 1.0


def test_convert_error(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_text("not a video")
    with pytest.raises(RuntimeError):
        Converter().convert(bad, tmp_path / "out", "mp3", "Voix")
    assert not list((tmp_path / "out").glob("*.mp3"))
