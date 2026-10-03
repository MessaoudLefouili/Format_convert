# Format Convert

Conversion locale de vidéos en MP3 ou M4A, avec interface graphique. ffmpeg est embarqué via `imageio-ffmpeg`, aucune installation externe.

## Lancer

```
pip install -r requirements.txt
python -m app.main
```

Ligne de commande: `python -m app.cli dossier_sortie mp3 Voix video1.mp4 video2.mkv`

## Presets

Voix 64 kbps mono, Standard 128 kbps, Haute 192 kbps.

## Tests

```
python -m pytest
```

## Build .exe (Windows)

```
build.bat
```
