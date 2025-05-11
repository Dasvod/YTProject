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
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

HF    = os.environ.get("HF_TOKEN")
OAUTH = os.environ["GOOGLE_OAUTH"]
PEXELS_KEY = os.environ.get("PEXELS_KEY")

# --- Funzioni di utilità ---

def clean_text(raw_text: str) -> str:
    """Rimuove prompt, markdown, emoji e caratteri speciali."""
    # 1) elimina simboli markdown
    text = re.sub(r'[`*_>#\-~]', '', raw_text)
    # 2) rimuove emoji (range Unicode)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticon
        "\U0001F300-\U0001F5FF"  # simboli
        "\U0001F680-\U0001F6FF"  # trasporti
        "\U0001F1E0-\U0001F1FF"  # bandiere
        "\u2600-\u2B55"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)
    # 3) trova inizio "1)" e scarta tutto ciò che lo precede
    m = re.search(r'^\s*1\)', text, flags=re.MULTILINE)
    if m:
        text = text[m.start():]
    # 4) normalizza spazi
    return ' '.join(text.split())

def gen_script(topic: str, mode: str) -> str:
    """
    Genera il testo via HF, senza fallback esterni.
    Riprova fino a 5 volte, poi raise.
    """
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
        if attempt < 5:
            time.sleep(5)
    raise RuntimeError(f"HF failed after 5 attempts: {last_error}")

def parse_paragraphs(script: str) -> list[str]:
    """
    Estrae ogni curiosità numerata come singolo paragrafo.
    Ritorna la lista di frasi (senza "1)", "2)", ...).
    """
    paras = []
    for m in re.finditer(r'^\s*\d\)\s*(.+)', script, flags=re.MULTILINE):
        paras.append(m.group(1).strip())
    return paras

def upload(path: str, title: str, desc: str, short: bool=False):
    creds = Credentials.from_authorized_user_info(json.loads(OAUTH))
    yt = build("youtube", "v3", credentials=creds)
    tags = [title, "curiosità", "trend"] + (["shorts"] if short else [])
    body = {
        "snippet": {
            "title": title + (" #shorts" if short else ""),
            "description": desc,
            "tags": tags
        },
        "status": {"privacyStatus": "public"}
    }
    yt.videos().insert(part="snippet,status", body=body, media_body=path).execute()

# --- Main pipeline ---

def run(mode: str):
    topic = pick_topic()
    script = gen_script(topic, mode)
    paras  = parse_paragraphs(script)

    segments = []
    for idx, para in enumerate(paras):
        # 1) Genera audio
        audio_file = f"audio_{idx}.wav"
        tts(para, audio_file)

        # 2) Scarica clip coerente (usa lo stesso fetch in video.py)
        from video import fetch_one_clip
        clip_file = fetch_one_clip(para, orientation = "portrait" if mode=="short" else "landscape")

        # 3) Allinea durata
        audio_clip = AudioFileClip(audio_file)
        duration   = audio_clip.duration
        video_clip = VideoFileClip(clip_file).subclip(0, duration).without_audio()

        # 4) Assegna audio al video
        segment = video_clip.set_audio(audio_clip)
        segments.append(segment)

    # 5) Unisci segmenti
    final = concatenate_videoclips(segments, method="compose")
    out   = f"{mode}.mp4"
    final.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

    # 6) Titolo e descrizione
    if mode=="short" and paras:
        title = f"{topic}: {paras[0]} e altre curiosità"
    else:
        title = topic
    desc = f"Scopri fatti e curiosità su {topic}! Guarda ora."

    # 7) Upload
    upload(out, title, desc, short=(mode=="short"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short","long"], required=True)
    run(p.parse_args().mode)
