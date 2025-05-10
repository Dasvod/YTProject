import subprocess, pathlib, sys, textwrap

MODEL = "it_IT-riccardo-medium.onnx"
URL   = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
         + MODEL)

def tts(text, wav_path="voice.wav"):
    m = pathlib.Path(MODEL)
    if not m.exists():                    # scarica il modello la 1ª volta
        subprocess.run(["wget", "-q", URL])
    subprocess.run([
        "piper", "--model", MODEL,
        "--output_file", wav_path,
        "--input_text", textwrap.shorten(text, 3000)
    ], check=True)

if __name__ == "__main__":
    tts(open(sys.argv[1]).read())
