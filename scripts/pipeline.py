import os, argparse, json, requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from trends import pick_topic
from voice import tts
from video import fetch_clips, make_video

HF = os.environ["HF_TOKEN"]
OAUTH = os.environ["GOOGLE_OAUTH"]


def gen_script(prompt, topic):
    try:
        r = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
            headers={"Authorization": f"Bearer {HF}"},
            json={"inputs": prompt},
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        return data[0].get("generated_text", "")
    except Exception:
        return (
            f"Ecco 3 curiosità su {topic}:\n"
            "1) Curiosità uno.\n"
            "2) Curiosità due.\n"
            "3) Curiosità tre.\n"
            "Iscriviti per altri contenuti!"
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
    yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=path
    ).execute()


def run(mode):
    topic = pick_topic()
    if mode == "short":
        prompt = (
            f"Script di 40s in italiano, tono energico, 3 curiosità numerate su {topic}."
        )
        title = f"3 curiosità su {topic} in 40s"
    else:
        prompt = (
            f"Testo di 8 minuti in italiano, 3 sezioni numerate su {topic}, tono conversazionale."
        )
        title = f"Scopri {topic}: dettagli in 8 minuti"

    script = gen_script(prompt, topic)
    wav = "voice.wav"
    tts(script, wav)
    clips = fetch_clips(topic, 3 if mode == "short" else 4)
    out = f"{mode}.mp4"
    make_video(clips, wav, vertical=(mode == "short"), out=out)
    upload(
        out,
        title,
        f"Scopri fatti incredibili su {topic}!",
        short=(mode == "short")
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short", "long"], required=True)
    run(p.parse_args().mode)
