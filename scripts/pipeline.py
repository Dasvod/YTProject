import os, argparse, json, requests, re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from trends import pick_topic
from voice  import tts
from video  import fetch_clips, make_video

HF    = os.environ["HF_TOKEN"]
OAUTH = os.environ["GOOGLE_OAUTH"]

def gen_script(prompt, mode, topic):
    """
    Genera uno script più ricco:
     - short: 180 parole, 5 curiosità numerate con mini-descrizioni
     - long: 800 parole, 5 sezioni numerate, esempi e conclusione
    """
    params = {"temperature": 0.7}
    if mode == "short":
        instr = (f"Scrivi un testo entusiasmante di circa 180 parole su {topic}, "
                 "diviso in 5 curiosità numerate (1–5), ognuna con almeno 2 frasi "
                 "che spieghino il punto in modo chiaro.")
    else:
        instr = (f"Scrivi un articolo/script di 800 parole sul tema {topic}, "
                 "con 5 sezioni numerate, ognuna che includa esempi concreti, e "
                 "una conclusione che inviti all'azione.")
    try:
        r = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
            headers={"Authorization": f"Bearer {HF}"}, 
            json={"inputs": instr, "parameters": params},
            timeout=60
        )
        r.raise_for_status()
        text = r.json()[0].get("generated_text", "")
        return text.strip() or instr  # se vuoto, torna il prompt stesso
    except Exception:
        # fallback robusto
        lines = []
        if mode == "short":
            for i in range(1,6):
                lines.append(f"{i}) Curiosità dettagliata su {topic} numero {i}.")
        else:
            lines = [f"Sezione {i}: approfondimento su {topic}, con esempi concreti."
                     for i in range(1,6)]
        return "\n".join(lines)

def parse_topics(script):
    """
    Estrae i titoli delle curiosità numerate dal testo generato.
    """
    return re.findall(r"^\s*\d+\)\s*([^.\n]+)", script, flags=re.MULTILINE)

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
    yt.videos().insert(part="snippet,status", body=body, media_body=path).execute()

def run(mode):
    topic = pick_topic()
    script = gen_script("", mode, topic)
    wav    = "voice.wav"
    tts(script, wav)

    # Estrai sottotemi e fetch clip per ognuno
    subtopics = parse_topics(script)
    if mode=="short":
        clips = []
        for st in subtopics:
            clips += fetch_clips(st.strip(), 1)
    else:
        clips = fetch_clips(topic, 4)

    out = f"{mode}.mp4"
    make_video(clips, wav, vertical=(mode=="short"), out=out)

    # Titolo dinamico
    title = (f"{topic}: " + subtopics[0] + " e altre curiosità"
             if subtopics else topic)
    desc  = f"Scopri di più su {topic} e guarda tutte le curiosità!"
    upload(out, title, desc, short=(mode=="short"))

if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["short","long"], required=True)
    run(p.parse_args().mode)
