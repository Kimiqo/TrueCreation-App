"""Real six-stem inference on a generated short signal; not a quality benchmark."""
from pathlib import Path
import numpy as np
import soundfile as sf
from app.config import DATA
from app.separation import separate

root = DATA / 'smoke'
root.mkdir(parents=True, exist_ok=True)
rate = 44100
t = np.arange(rate * 2) / rate
audio = 0.15 * np.sin(2 * np.pi * 220 * t) + 0.08 * np.sin(2 * np.pi * 440 * t)
source = root / 'mix.wav'
sf.write(source, np.column_stack([audio, audio]), rate)
paths = separate(source, root / 'separated')
for name, path in paths.items():
    info = sf.info(path)
    print(f'{name}: {info.frames} frames, {info.samplerate} Hz, {info.channels} channels')
print('Actual model inference completed; this does not establish music separation quality.')
