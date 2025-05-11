import subprocess, os
from gtts import gTTS

def tts(text, wav_path="voice.wav"):
    # Genera audio con gTTS
    try:
        tts = gTTS(text, lang='it')
        tmp_mp3 = "voice.mp3"
        tts.save(tmp_mp3)
        # converte in WAV
        subprocess.run([
            "ffmpeg", "-y",
            "-i", tmp_mp3,
            "-ar", "44100",
            wav_path
        ], check=True)
        os.remove(tmp_mp3)
    except Exception:
        # fallback 1s di silenzio
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "1", wav_path
        ], check=True)

if __name__ == "__main__":
    import sys
    tts(sys.stdin.read())
