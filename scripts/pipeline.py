import os, argparse, json, requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from trends import pick_topic
from voice  import tts
from video  import fetch_clips, make_video

HF   = os.environ["HF_TOKEN"]
OAUTH= os.environ["GOOGLE_OAUTH"]

def gen_script(prompt):
    payload = {"inputs": prompt,
               "parameters": {"temperature": 0.8, "max_new_tokens": 280}}
    r = requests.post(
        "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
        headers={"Authorization": f"Bearer {HF}"}, json=payload, timeout=60)
    return r.json()[0]["generated_text"]

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
    topic   = pick_topic()
    prompt  = (f"Scrivi {'1000' if mode=='long' else '140'} parole, "
               f"tono entusiasta, su {topic}. "
               f"3 curiosità numerate, chiusura forte.")
    script  = gen_script(prompt)
    wav     = "voice.wav"; tts(script, wav)
    clips   = fetch_clips(topic, 4 if mode=="long" else 3)
    out     = f"{mode}.mp4"
    make_video(clips, wav, vertical=(mode=="short"), out=out)
    upload(out, topic, f"Scopri di più su {topic}!", short=(mode=="short"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short", "long"], required=True)
    run(p.parse_args().mode)
