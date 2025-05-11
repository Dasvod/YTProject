import os
import random
import requests
import moviepy.editor as mp
from PIL import Image

# Patch per PIL≥10: ANTIALIAS non esiste più, usiamo LANCZOS
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
    # 1) Carica e taglia ogni clip a 10s, senza audio
    vc = [mp.VideoFileClip(c).subclip(0, 10).without_audio() for c in clips]

    # 2) Se è short (vertical), ridimensiona e manterrai massimo 60s
    if vertical:
        vc = [c.resize(height=1920).resize(width=1080) for c in vc]

    # 3) Concatenazione
    video = mp.concatenate_videoclips(vc, method="compose")

    # 4) Carica l’audio
    audio_clip = mp.AudioFileClip(audio)

    # 5) Se l’audio è più corto del video, trimma il video alla durata dell’audio
    if video.duration > audio_clip.duration:
        video = video.subclip(0, audio_clip.duration)

    # 6) Imposta l’audio e, nel caso di short, rifinisci a ≤60s
    video = video.set_audio(audio_clip)
    if vertical and video.duration > 60:
        video = video.subclip(0, 60)

    # 7) Esporta
    video.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

if __name__ == "__main__":
    import sys
    # sys.argv: [query, wav_path, vertical_flag(0|1), output_filename]
    make_video(
      fetch_clips(sys.argv[1]),
      sys.argv[2],
      vertical=bool(int(sys.argv[3])),
      out=sys.argv[4]
    )
