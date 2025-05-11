import os
import random
import requests
import moviepy.editor as mp
from PIL import Image

# Patch per PIL≥10: definisce ANTIALIAS come LANCZOS, altrimenti MoviePy crasha
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

PEXELS = os.environ["PEXELS_KEY"]

def fetch_clips(query, n=3):
    r = requests.get(
        f"https://api.pexels.com/videos/search?query={query}&per_page=15",
        headers={"Authorization": PEXELS}, timeout=30
    ).json()
    vids = random.sample(r.get("videos", []), k=min(n, len(r.get("videos", []))))
    out = []
    for i, v in enumerate(vids):
        url = v["video_files"][0]["link"]
        fn = f"clip_{i}.mp4"
        with open(fn, "wb") as f:
            f.write(requests.get(url, timeout=60).content)
        out.append(fn)
    return out

def make_video(clips, audio, vertical=False, out="output.mp4"):
    # Carica i clip senza audio e taglia a 10s ciascuno
    vc = [mp.VideoFileClip(c).subclip(0, 10).without_audio() for c in clips]
    # Se è short (vertical), ridimensiona e limita a 60s
    if vertical:
        vc = [c.resize(height=1920).resize(width=1080) for c in vc]
    # Concatenazione
    video = mp.concatenate_videoclips(vc, method="compose")
    # Aggiunge l'audio
    video = video.set_audio(mp.AudioFileClip(audio))
    # Se short, taglia a massimo 60s
    if vertical:
        video = video.subclip(0, 60)
    # Esporta
    video.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

if __name__ == "__main__":
    import sys
    # argv: query, path_wav, vertical_flag(0/1), out_filename
    make_video(
        fetch_clips(sys.argv[1]),
        sys.argv[2],
        vertical=bool(int(sys.argv[3])),
        out=sys.argv[4]
    )
