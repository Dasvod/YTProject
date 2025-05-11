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
# Import PIL per patchare ANTIALIAS
from PIL import Image
# Se ANTIALIAS non esiste (Pillow>=10), alias in LANCZOS
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

HF         = os.environ.get("HF_TOKEN")
OAUTH      = os.environ["GOOGLE_OAUTH"]
PEXELS_KEY = os.environ.get("PEXELS_KEY")

# Dimensioni target per YouTube Short
FRAME_W, FRAME_H = 1080, 1920

def clean_text(raw_text: str) -> str:
    lines = raw_text.splitlines()
    cleaned = []
    emoji_pattern = re.compile(
        "[" 
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u2B55"
        "]+",
        flags=re.UNICODE
    )
    for line in lines:
        line = re.sub(r'[`*_>#~-]', '', line)
        line = emoji_pattern.sub('', line)
        cleaned.append(line.strip())
    text = "\n".join(cleaned)
    m = re.search(r'^\s*1[.)]', text, flags=re.MULTILINE)
    if m:
        text = text[m.start():]
    return text.strip()

def gen_script(topic: str, mode: str) -> str:
    if not HF:
        raise RuntimeError("HF_TOKEN non impostato!")
    prompt = (
        f"Scrivi un testo entusiasmante di circa 150 parole su '{topic}', "
        "diviso in 5 curiosità numerate, ognuna con almeno 2 frasi di spiegazione."
        if mode == "short" else
        f"Sviluppa un articolo di 800 parole su '{topic}', "
        "con 5 sezioni numerate, esempi concreti e conclusione."
    )
    headers = {"Authorization": f"Bearer {HF}"}
    payload = {"inputs": prompt, "parameters": {"temperature": 0.7}}
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

    last_error = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            text = data[0].get("generated_text", "").strip()
            if text:
                return clean_text(text)
            last_error = RuntimeError(f"Empty on attempt {attempt}")
        except Exception as e:
            last_error = e
        time.sleep(5)
    raise RuntimeError(f"HF failed after 5 attempts: {last_error}")

def parse_paragraphs(script: str) -> list[str]:
    paras = [
        m.group(1).strip()
        for m in re.finditer(r'^\s*\d+[.)]\s*(.+)', script, flags=re.MULTILINE)
    ]
    if not paras:
        paras = [script.replace('\n', ' ')]
    return paras

def safe_title(raw_title: str, limit: int = 100) -> str:
    title = raw_title.replace('\n', ' ').strip()
    if len(title) > limit:
        title = title[: limit-3].rstrip() + "..."
    if not title:
        raise RuntimeError("Titolo video vuoto dopo pulizia!")
    return title

def upload(path: str, raw_title: str, desc: str, short: bool = False):
    suffix = " #shorts" if short else ""
    full_title = f"{raw_title}{suffix}"
    title = safe_title(full_title)
    creds = Credentials.from_authorized_user_info(json.loads(OAUTH))
    yt = build("youtube", "v3", credentials=creds)
    tags = [title, "curiosità", "trend"] + (["shorts"] if short else [])
    body = {
        "snippet": {
            "title": title,
            "description": desc,
            "tags": tags
        },
        "status": {"privacyStatus": "public"}
    }
    yt.videos().insert(part="snippet,status", body=body, media_body=path).execute()

def run(mode: str):
    topic = pick_topic()
    script = gen_script(topic, mode)
    paras  = parse_paragraphs(script)

    # Costruisci descrizione coerente
    desc_lines = [f"{i+1}) {p}" for i, p in enumerate(paras[:5])]
    desc = f"Scopri 5 curiosità su {topic}:\n" + "\n".join(desc_lines)

    segments = []
    for idx, para in enumerate(paras):
        audio_file = f"audio_{idx}.wav"
        tts(para, audio_file)

        from video import fetch_one_clip
        clip_file = fetch_one_clip(
            para,
            orientation="portrait" if mode=="short" else "landscape"
        )

        audio_clip = AudioFileClip(audio_file)
        duration   = audio_clip.duration
        v = VideoFileClip(clip_file).subclip(0, duration).without_audio()

        if mode=="short":
            # scala in base all'altezza
            v = v.resize(height=FRAME_H)
            # se troppo stretto, centra su sfondo nero
            if v.w < FRAME_W:
                bg = ColorClip(size=(FRAME_W, FRAME_H), color=(0,0,0), duration=duration)
                v = CompositeVideoClip([bg, v.set_position("center")])

        segment = v.set_audio(audio_clip)
        segments.append(segment)

    final = concatenate_videoclips(segments, method="compose")
    out   = f"{mode}.mp4"
    final.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

    raw_title = (
        f"{topic}: {paras[0]} e altre curiosità"
        if mode=="short" and paras else topic
    )
    upload(out, raw_title, desc, short=(mode=="short"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short","long"], required=True)
    run(p.parse_args().mode)
