import os
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

def wiki_fallback(topic):
    """Recupera un estratto da Wikipedia IT se HF fallisce."""
    try:
        url = f"https://it.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ','_')}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("extract", f"Ecco alcune informazioni su {topic}.")
    except Exception:
        return f"Ecco alcune informazioni interessanti su {topic}."

def gen_script(topic, mode):
    """
    Genera lo script con HF; se fallisce, usa Wikipedia.
    Short = 5 curiosità da ~30 parole ciascuna.
    Long  = 5 sezioni da ~160 parole ciascuna.
    """
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

    if HF:
        try:
            resp = requests.post(
                "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
                headers={"Authorization": f"Bearer {HF}"},
                json={"inputs": prompt, "parameters": {"temperature":0.7}},
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            text = data[0].get("generated_text","").strip()
            if text:
                return text
        except Exception:
            pass

    # fallback su Wikipedia
    return wiki_fallback(topic)

def parse_topics(script):
    """
    Estrae i titoli delle curiosità/sezioni numerate.
    Ritorna lista di sottotemi.
    """
    return re.findall(r"^\s*\d+\)\s*([^.\n]+)", script, flags=re.MULTILINE)

def upload(path, title, desc, short=False):
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

def run(mode):
    topic = pick_topic()
    script = gen_script(topic, mode)
    wav    = "voice.wav"
    tts(script, wav)

    # Sottotemi per fetch clip
    subtopics = parse_topics(script)
    clips = []
    if mode == "short" and subtopics:
        for st in subtopics[:5]:
            clips += fetch_clips(st.strip(), 1)
    else:
        clips = fetch_clips(topic, 4)

    out = f"{mode}.mp4"
    make_video(clips, wav, vertical=(mode=="short"), out=out)

    # Titolo + descrizione
    if mode=="short" and subtopics:
        title = f"{topic}: {subtopics[0].strip()} e altre curiosità"
    else:
        title = topic
    desc = f"Scopri fatti e curiosità su {topic}! Guarda ora."

    upload(out, title, desc, short=(mode=="short"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short","long"], required=True)
    run(p.parse_args().mode)
