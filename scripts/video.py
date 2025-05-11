import os
import requests
import random

PEXELS_KEY = os.environ["PEXELS_KEY"]

def fetch_clips(query: str, n: int = 3, orientation: str = "landscape") -> list[str]:
    """
    Restituisce fino a n clip coerenti con la query.
    """
    headers = {"Authorization": PEXELS_KEY}
    url = (
        f"https://api.pexels.com/videos/search"
        f"?query={query}&per_page={n}&orientation={orientation}"
    )
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json().get("videos", [])
    out = []
    for vid in random.sample(data, k=min(n, len(data))):
        file_url = vid["video_files"][0]["link"]
        fn = f"clip_{vid['id']}.mp4"
        with open(fn, "wb") as f:
            f.write(requests.get(file_url, timeout=60).content)
        out.append(fn)
    return out

def fetch_one_clip(query: str, orientation: str = "landscape") -> str:
    """
    Scarica un singolo clip (il primo risultato) per la query.
    """
    clips = fetch_clips(query, n=1, orientation=orientation)
    return clips[0] if clips else None
