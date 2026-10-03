@echo off
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --name FormatConvert ^
  --collect-all tkinterdnd2 --collect-all customtkinter --collect-all imageio_ffmpeg ^
  app\main.py
echo Build termine: dist\FormatConvert\FormatConvert.exe
