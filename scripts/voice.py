import subprocess
from gtts import gTTS

def tts(text: str, out_wav: str):
    """
    Genera audio in inglese con gTTS → mp3 → wav (ffmpeg richiesto).
    """
    mp3 = out_wav.replace('.wav','.mp3')
    gTTS(text=text, lang='en').save(mp3)
    # converti in wav
    subprocess.run([
        'ffmpeg','-y','-i', mp3,
        '-ar','24000','-ac','1', out_wav
    ], check=True)
