import os
import time
import argparse
import json
import requests
import re

from PIL import Image
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from trends import pick_topic
from voice import tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip,
    concatenate_videoclips, CompositeVideoClip, ColorClip
)

# Patch per Pillow>=10
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

HF         = os.environ.get("HF_TOKEN")
OAUTH      = os.environ["GOOGLE_OAUTH"]
PEXELS_KEY = os.environ.get("PEXELS_KEY")

# Frame target per Short (vertical)
FRAME_W, FRAME_H = 1080, 1920

def clean_text(raw: str) -> str:
    """
    Rimuove markdown/emoji e tutto ciò che precede la prima curiosità numerata.
    """
    # elimina simboli markdown e emoji
    lines = raw.splitlines()
    emoji_re = re.compile("[\U0001F600-\U0001F64F"
                          "\U0001F300-\U0001F5FF"
                          "\U0001F680-\U0001F6FF"
                          "\U0001F1E0-\U0001F1FF"
                          "\u2600-\u2B55]+", flags=re.UNICODE)
    cleaned = []
    for L in lines:
        L = re.sub(r"[`*_>#~-]", "", L)
        L = emoji_re.sub("", L)
        cleaned.append(L.strip())
    text = "\n".join(cleaned)
    # taglia via tutto prima di "1)" o "1."
    m = re.search(r"^\s*1[.)]", text, flags=re.MULTILINE)
    if m:
        return text[m.start():].strip()
    return text.strip()

def gen_script(topic: str, mode: str) -> str:
    """
    Chiama HF e ritorna testo già pulito dalle cose inutili.
    """
    if not HF:
        raise RuntimeError("HF_TOKEN not set!")
    prompt = (
        f"Write an engaging ~150-word English text about '{topic}', "
        "in 5 numbered curiosities (1–5)."
        if mode == "short" else
        f"Write an 800-word in-depth English article about '{topic}', "
        "in 5 numbered sections."
    )
    headers = {"Authorization": f"Bearer {HF}"}
    payload = {"inputs": prompt, "parameters": {"temperature": 0.7}}
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

    last_err = None
    for i in range(5):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            out = r.json()[0].get("generated_text", "").strip()
            if out:
                return clean_text(out)
            last_err = RuntimeError(f"empty output on try {i+1}")
        except Exception as e:
            last_err = e
        time.sleep(5)
    raise RuntimeError(f"HF failed after 5 attempts: {last_err}")

def parse_paragraphs(script: str) -> list[str]:
    """
    Divide il testo pulito in paragrafi numerati 1), 2), ….
    """
    parts = re.split(r"^\s*\d+[.)]\s*", script, flags=re.MULTILINE)
    # il primo elemento è testo prima di 1), togliamolo
    paras = [p.strip().replace("\n", " ") for p in parts[1:] if p.strip()]
    return paras or []

def fetch_clip_for(para: str, orientation: str) -> str:
    """
    Usa le prime 3 parole come query per Pexels.
    """
    key = " ".join(para.split()[:3])
    from video import fetch_one_clip
    return fetch_one_clip(key, orientation=orientation)

def upload(path: str, title: str, desc: str, short: bool=False):
    creds = Credentials.from_authorized_user_info(json.loads(OAUTH))
    yt    = build("youtube", "v3", credentials=creds)
    suffix = " #shorts" if short else ""
    full_title = (title + suffix).replace("\n", " ")
    if len(full_title) > 100:
        full_title = full_title[:97].rstrip() + "..."
    body = {
        "snippet": {
            "title": full_title,
            "description": desc,
            "tags": [title, "curiosity", "trend"] + (["shorts"] if short else [])
        },
        "status": {"privacyStatus":"public"}
    }
    yt.videos().insert(part="snippet,status",
                       body=body, media_body=path).execute()

def run(mode: str):
    topic = pick_topic()
    script = gen_script(topic, mode)
    paras = parse_paragraphs(script)

    # descrizione elenco
    desc_lines = [f"{i+1}) {p}" for i,p in enumerate(paras[:5])]
    desc = f"5 curiosities about {topic}:\n" + "\n".join(desc_lines)

    segments = []
    for idx, para in enumerate(paras):
        # TTS in inglese
        audio_file = f"audio_{idx}.wav"
        tts(para, audio_file)

        # Fetch clip coerente
        clip_file = fetch_clip_for(
            para,
            orientation="portrait" if mode=="short" else "landscape"
        )

        # Sincronizza durata audio/video
        ac = AudioFileClip(audio_file)
        vc = VideoFileClip(clip_file).subclip(0, ac.duration).without_audio()

        # Up-scale/pad per vertical shorts
        if mode=="short":
            vc = vc.resize(height=FRAME_H)
            if vc.w < FRAME_W:
                bg = ColorClip((FRAME_W,FRAME_H),(0,0,0),duration=ac.duration)
                vc = CompositeVideoClip([bg, vc.set_position("center")])

        segments.append(vc.set_audio(ac))

    # unisci segmenti
    final = concatenate_videoclips(segments, method="compose")
    out   = f"{mode}.mp4"
    final.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

    # Titolo basato sul topic e prima curiosità
    title = f"{topic}: {paras[0]}" if paras else topic
    upload(out, title, desc, short=(mode=="short"))

if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short","long"], required=True)
    run(p.parse_args().mode)
