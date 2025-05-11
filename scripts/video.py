import os
import requests
import random

PEXELS_KEY = os.environ["PEXELS_KEY"]

def fetch_clips(query: str, n: int = 3, orientation: str = "landscape") -> list[str]:
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
    clips = fetch_clips(query, n=1, orientation=orientation)
    if not clips:
        raise RuntimeError(f"No clip found for \"{query}\"")
    return clips[0]
