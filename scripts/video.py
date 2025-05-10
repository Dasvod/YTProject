import os, random, requests, moviepy.editor as mp

PEXELS = os.environ["PEXELS_KEY"]

def fetch_clips(query, n=3):
    r = requests.get(
        f"https://api.pexels.com/videos/search?query={query}&per_page=15",
        headers={"Authorization": PEXELS}, timeout=30).json()
    vids = random.sample(r["videos"], k=min(n, len(r["videos"])))
    out  = []
    for i, v in enumerate(vids):
        url = v["video_files"][0]["link"]
        fn  = f"clip_{i}.mp4"
        open(fn, "wb").write(requests.get(url, timeout=60).content)
        out.append(fn)
    return out

def make_video(clips, audio, vertical=False, out="output.mp4"):
    vc = [mp.VideoFileClip(c).subclip(0, 10).without_audio() for c in clips]
    if vertical:
        vc = [c.resize(height=1920).resize(width=1080) for c in vc]
    video = mp.concatenate_videoclips(vc, method="compose")
    video = video.set_audio(mp.AudioFileClip(audio))
    if vertical:
        video = video.subclip(0, 60)      # Shorts ≤60 s
    video.write_videofile(out, fps=30, codec="libx264", preset="veryfast")

if __name__ == "__main__":
    import sys
    make_video(fetch_clips(sys.argv[1]), sys.argv[2],
               vertical=bool(int(sys.argv[3])), out=sys.argv[4])
