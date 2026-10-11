"""Self-hosted separation adapters. Drum expansion intentionally unconfigured."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol
import soundfile as sf
from .config import MODEL, STEMS

class DrumSeparator(Protocol):
    def separate(self, drums: Path, output: Path) -> dict[str, Path]: ...

DRUM_SEPARATOR: DrumSeparator | None = None

def available():
    return importlib.util.find_spec('demucs') is not None

def separate(source: Path, output: Path):
    if not available():
        raise ValueError('Separation engine not installed. Install backend/requirements-separation.txt, then restart the worker.')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'separation.log').open('w') as log:
        # CPU is portable for initial development. First use downloads pretrained weights.
        env = dict(os.environ)
        env.setdefault('HF_HOME', str(output.resolve().parents[1] / 'model-cache' / 'huggingface'))
        env.setdefault('TORCH_HOME', str(output.resolve().parents[1] / 'model-cache' / 'torch'))
        env.setdefault('OMP_NUM_THREADS', '4')
        try:
            subprocess.run([sys.executable, '-m', 'demucs', '-n', MODEL, '-d', 'cpu', '--shifts', '0', '--clip-mode', 'clamp', '-o', str(output), str(source)], env=env, stdout=log, stderr=log, check=True, timeout=3600)
        except subprocess.CalledProcessError as exc:
            tail = (output / 'separation.log').read_text(errors='replace')[-1200:]
            raise ValueError(f'Separation failed. See the project separation.log. {tail}') from exc
    base = output / MODEL / source.stem
    paths = {stem: base / f'{stem}.wav' for stem in STEMS}
    original = sf.info(source)
    for name, path in paths.items():
        if not path.exists():
            raise ValueError(f'Separation did not produce the expected {name} stem.')
        info = sf.info(path)
        if info.samplerate != original.samplerate or abs(info.frames - original.frames) > 1:
            raise ValueError('Separated stems do not share the source timeline.')
    return paths
