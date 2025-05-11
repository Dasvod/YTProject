import os
import time
import argparse
import json
import requests
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from trends import pick_topic
from voice import tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip,
    concatenate_videoclips, CompositeVideoClip, ColorClip
)
from PIL import Image

# Patch PIL≥10
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

HF         = os.environ.get("HF_TOKEN")
OAUTH      = os.environ["GOOGLE_OAUTH"]
PEXELS_KEY = os.environ.get("PEXELS_KEY")

FRAME_W, FRAME_H = 1080, 1920  # per Shorts verticali

def gen_script(topic: str, mode: str) -> str:
    """
    Genera un testo in inglese con sub-titles chiari per ciascuna curiosity:
      1) TITLE: explanation…
    """
    if not HF:
        raise RuntimeError("HF_TOKEN not set!")

    prompt = (
        f"Write an engaging ~150-word text about '{topic}' in English, "
        "structured as 5 numbered curiosities. "
        "Each item must start with a short TITLE (3-5 words in ALL CAPS), "
        "followed by a colon and 2–3 sentences of explanation."
        if mode == "short" else
        f"Write an 800-word in-depth article about '{topic}' in English, "
        "with 5 numbered sections. Each section must start with a heading "
        "(3–5 words in ALL CAPS), then detailed paragraphs and a conclusion."
    )

    headers = {"Authorization": f"Bearer {HF}"}
    payload = {"inputs": prompt, "parameters": {"temperature": 0.7}}
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

    last_error = None
    for i in range(5):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            out = r.json()[0].get("generated_text", "").strip()
            if out:
                return out
            last_error = RuntimeError(f"empty output on try {i+1}")
        except Exception as e:
            last_error = e
        time.sleep(5)
    raise RuntimeError(f"HF generation failed: {last_error}")

def parse_items(script: str) -> list[tuple[str,str]]:
    """
    Da un script come:
      1) BRIDGE DESIGN: Bridges are built…
      2) ...
    Estrae [(title, explanation), ...].
    """
    items = []
    for m in re.finditer(r'^\s*\d+\)\s*([A-Z0-9 ]{3,50}):\s*(.+?)(?=(?:^\s*\d+\))|\Z)',
                         script, flags=re.MULTILINE|re.DOTALL):
        title       = m.group(1).strip().title()
        explanation = m.group(2).strip().replace('\n',' ')
        items.append((title, explanation))
    if not items:
        # fallback: tutto come un unico blocco
        items = [("TOPIC", script.replace('\n',' '))]
    return items

def safe_title(raw_title: str, limit: int=100) -> str:
    t = raw_title.replace('\n',' ').strip()
    return (t if len(t)<=limit else t[:limit-3].rstrip()+"...")

def upload(path: str, title: str, desc: str, short: bool=False):
    creds = Credentials.from_authorized_user_info(json.loads(OAUTH))
    yt    = build("youtube","v3",credentials=creds)
    title = safe_title(title + (" #shorts" if short else ""))
    tags  = [title, "curiosity", "trend"] + (["shorts"] if short else [])
    body  = {
        "snippet": {"title": title,"description": desc,"tags": tags},
        "status":  {"privacyStatus":"public"}
    }
    yt.videos().insert(part="snippet,status", body=body, media_body=path).execute()

def run(mode: str):
    # 1) Scegli topic casuale
    topic  = pick_topic()  # ora pick_topic può includere random Wiki o HF trends
    # 2) Genera script
    script = gen_script(topic, mode)
    # 3) Parso titoli+spiegazioni
    items  = parse_items(script)

    # 4) Build description più coerente
    desc = f"5 curiosities about {topic}:\n" + "\n".join(f"{i+1}) {t}" for i,(t,_) in enumerate(items[:5]))

    segments = []
    for idx, (title, text) in enumerate(items):
        # 5) Audio in inglese
        audio = f"audio_{idx}.wav"
        tts(text, audio)

        # 6) Video coerente sul title
        from video import fetch_one_clip
        clip = fetch_one_clip(title, orientation="portrait" if mode=="short" else "landscape")

        # 7) Sincronizza durata
        ac = AudioFileClip(audio)
        vc = VideoFileClip(clip).subclip(0, ac.duration).without_audio()

        # 8) Pad/up-scale vertical
        if mode=="short":
            vc = vc.resize(height=FRAME_H)
            if vc.w < FRAME_W:
                bg  = ColorClip((FRAME_W,FRAME_H),(0,0,0),duration=ac.duration)
                vc  = CompositeVideoClip([bg,vc.set_position("center")])

        segments.append(vc.set_audio(ac))

    # 9) Concatenazione
    final = concatenate_videoclips(segments, method="compose")
    out   = f"{mode}.mp4"
    final.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

    # 10) Upload
    title = f"{topic}: {items[0][0]}"
    upload(out, title, desc, short=(mode=="short"))

if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode",choices=["short","long"],required=True)
    run(p.parse_args().mode)
