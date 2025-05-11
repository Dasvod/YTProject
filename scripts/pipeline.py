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
from video import fetch_clips, make_video

HF    = os.environ.get("HF_TOKEN")
OAUTH = os.environ["GOOGLE_OAUTH"]

def gen_script(topic: str, mode: str) -> str:
    """
    Genera lo script tramite Hugging Face Inference API.
    Ritenta fino a 5 volte in caso di errori o risposte vuote,
    con ritardo di 5 secondi tra i tentativi. Se poi non va,
    solleva un'eccezione per bloccare la pipeline.
    """
    if not HF:
        raise RuntimeError("HF_TOKEN non impostato!")

    # Costruzione del prompt
    if mode == "short":
        prompt = (
            f"Scrivi un testo entusiasmante di circa 150 parole su '{topic}', "
            "diviso in 5 curiosità numerate, ognuna con almeno 2 frasi di spiegazione."
        )
    else:
        prompt = (
            f"Sviluppa un articolo/script di 800 parole sul tema '{topic}', "
            "con 5 sezioni numerate, esempi concreti, e una conclusione coinvolgente."
        )

    headers = {"Authorization": f"Bearer {HF}"}
    payload = {"inputs": prompt, "parameters": {"temperature": 0.7}}

    last_error = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(
                "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
                headers=headers,
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            text = data[0].get("generated_text", "").strip()
            if text:
                return text
            else:
                last_error = RuntimeError(f"Empty generation on attempt {attempt}")
        except Exception as e:
            last_error = e

        # se non è l'ultimo tentativo, attendi e riprova
        if attempt < 5:
            time.sleep(5)

    # Dopo 5 tentativi, falliamo
    raise RuntimeError(f"HF generation failed after 5 attempts: {last_error}")

def parse_topics(script: str) -> list[str]:
    """
    Estrae i titoli delle curiosità/sezioni numerate dal testo generato.
    """
    return re.findall(r"^\s*\d+\)\s*([^.\n]+)", script, flags=re.MULTILINE)

def upload(path: str, title: str, desc: str, short: bool = False):
    creds = Credentials.from_authorized_user_info(json.loads(OAUTH))
    yt = build("youtube", "v3", credentials=creds)
    tags = [title, "curiosità", "trend"]
    if short:
        tags.append("shorts")
    body = {
        "snippet": {
            "title": title + (" #shorts" if short else ""),
            "description": desc,
            "tags": tags
        },
        "status": {"privacyStatus": "public"}
    }
    yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=path
    ).execute()

def run(mode: str):
    topic = pick_topic()
    # Genera lo script (potrebbe sollevare se HF non risponde)
    script = gen_script(topic, mode)

    wav = "voice.wav"
    tts(script, wav)

    # Estrai sottotemi e recupera clip
    subtopics = parse_topics(script)
    clips = []
    if mode == "short" and subtopics:
        for st in subtopics[:5]:
            clips += fetch_clips(st.strip(), 1)
    else:
        clips = fetch_clips(topic, 4)

    out = f"{mode}.mp4"
    make_video(clips, wav, vertical=(mode == "short"), out=out)

    # Titolo e descrizione
    if mode == "short" and subtopics:
        title = f"{topic}: {subtopics[0].strip()} e altre curiosità"
    else:
        title = topic
    desc = f"Scopri fatti e curiosità su {topic}! Guarda ora."

    # Upload come Short se mode=="short"
    upload(out, title, desc, short=(mode == "short"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short","long"], required=True)
    run(p.parse_args().mode)
