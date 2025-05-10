import os, argparse, json, requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from trends import pick_topic
from voice  import tts
from video  import fetch_clips, make_video

HF   = os.environ["HF_TOKEN"]
OAUTH= os.environ["GOOGLE_OAUTH"]

def gen_script(prompt, topic):
    """
    Prova a generare lo script via HF Inference.
    In caso di errore o JSON invalido, torna un fallback statico.
    """
    try:
        payload = {
            "inputs": prompt,
            "parameters": {"temperature": 0.8, "max_new_tokens": 280}
        }
        r = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
            headers={"Authorization": f"Bearer {HF}"}, json=payload, timeout=60
        )
        r.raise_for_status()
        data = r.json()
        return data[0].get("generated_text", "")
    except Exception:
        # Fallback breve ma funzionale
        return (
            f"Ecco tre curiosità su {topic}:\n"
            "1) Curiosità numero uno.\n"
            "2) Curiosità numero due.\n"
            "3) Curiosità numero tre.\n"
            "Grazie per aver visto, iscriviti per altri contenuti!"
        )

def upload(path, title, desc, short=False):
    creds = Credentials.from_authorized_user_info(json.loads(OAUTH))
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title + (" #shorts" if short else ""),
            "description": desc,
            "tags": [title, "curiosità", "trend"]
        },
        "status": {"privacyStatus": "public"}
    }
    yt.videos().insert(part="snippet,status",
                       body=body, media_body=path).execute()

def run(mode):
    topic = pick_topic()
    if mode == "long":
        prompt = (
            f"Scrivi uno script da 1000 parole, tono conversazionale, "
            f"3 sezioni numerate con esempi, conclusione forte. Tema: {topic}"
        )
    else:
        prompt = (
            f"Script da 140 parole, tono entusiasmo, 3 curiosità numerate. Tema: {topic}"
        )
    script = gen_script(prompt, topic)
    wav = "voice.wav"
    tts(script, wav)
    clips = fetch_clips(topic, 4 if mode == "long" else 3)
    out = f"{mode}.mp4"
    make_video(clips, wav, vertical=(mode == "short"), out=out)
    upload(out, topic, f"Scopri fatti pazzeschi su {topic}!", short=(mode == "short"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short", "long"], required=True)
    run(p.parse_args().mode)
