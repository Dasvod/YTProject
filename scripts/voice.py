import subprocess, pathlib, sys, textwrap

MODEL = "it_IT-riccardo-medium.onnx"
URL   = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/" + MODEL
)

def tts(text, wav_path="voice.wav"):
    # Scarica il modello se manca
    m = pathlib.Path(MODEL)
    if not m.exists():
        try:
            subprocess.run(["wget", "-q", URL], check=True)
        except Exception:
            # se il download fallisce, prosegui e lascia che piper fallisca gestendolo nel blocco successivo
            pass
    try:
        # Prova a generare la voce con Piper
        subprocess.run([
            "piper", "--model", MODEL,
            "--output_file", wav_path,
            "--input_text", textwrap.shorten(text, 3000)
        ], check=True)
    except Exception:
        # Fallback: genera 1 s di silenzio per non bloccare la pipeline
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "1", wav_path
        ], check=True)

if __name__ == "__main__":
    tts(open(sys.argv[1]).read())
