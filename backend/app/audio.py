import json
import math
import shutil
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from .config import MAX_SECONDS

def probe(path: Path):
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
        raise ValueError('FFmpeg is missing. Install FFmpeg to process audio.')
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('This file could not be decoded as audio.')
    value = json.loads(result.stdout)
    duration = float(value.get('format', {}).get('duration', 0))
    if not any(s.get('codec_type') == 'audio' for s in value.get('streams', [])):
        raise ValueError('The uploaded file has no audio stream.')
    if not math.isfinite(duration) or duration <= 0 or duration > MAX_SECONDS:
        raise ValueError(f'Use a track between 1 second and {MAX_SECONDS // 60} minutes for this local MVP.')
    return duration

def decode(source: Path, target: Path):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source), '-vn', '-ac', '2', '-ar', '44100', '-t', str(MAX_SECONDS), '-c:a', 'pcm_s16le', str(target)], check=True, capture_output=True, timeout=120)

def profile(path: Path, start=0.0, end=None):
    with sf.SoundFile(path) as f:
        rate = f.samplerate
        begin = int(start * rate)
        stop = min(len(f), int(end * rate)) if end is not None else len(f)
        f.seek(begin)
        samples = f.read(max(0, stop - begin), dtype='float32', always_2d=True)
    if not len(samples):
        raise ValueError('The selected passage is empty.')
    mono = samples.mean(axis=1)
    rms = float(np.sqrt(np.mean(samples.astype('float64') ** 2)))
    bins = np.array_split(mono, min(240, len(mono)))
    peaks = [round(float(np.max(np.abs(b))), 4) for b in bins]
    # Bound FFT work to the first 4 seconds; this is a measurement, not instrument attribution.
    window = mono[:min(len(mono), rate * 4)]
    power = np.abs(np.fft.rfft(window * np.hanning(len(window))))
    freqs = np.fft.rfftfreq(len(window), 1 / rate)
    centroid = float(np.sum(freqs * power) / power.sum()) if power.sum() > 0 else None
    return {'duration': round(len(samples) / rate, 3), 'rms_dbfs': round(20 * math.log10(rms), 2) if rms > 0 else None,
            'spectral_centroid_hz': round(centroid, 1) if centroid is not None else None,
            'waveform': peaks, 'tempo_bpm': None, 'key': None, 'method': 'signal-measurements-v1'}

def musical_analysis(path: Path):
    value = profile(path)
    try:
        import librosa
        y, sr = librosa.load(path, sr=22050, mono=True)
        if np.max(np.abs(y)) < 1e-5:
            return value
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        value['tempo_bpm'] = round(bpm, 1) if bpm > 0 else None
        # Chroma-profile baseline; always presented as an estimate.
        chroma = librosa.feature.chroma_stft(y=y, sr=sr).mean(axis=1)
        major = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
        minor = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
        candidates = [(float(np.corrcoef(chroma, np.roll(p, k))[0,1]), k, mode) for mode,p in [('major',major),('minor',minor)] for k in range(12)]
        score, key, mode = max(candidates)
        if math.isfinite(score) and score > 0.5:
            value['key'] = f'{["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][key]} {mode}'
        value['method'] = 'librosa-beat-and-chroma-baseline-v1'
    except Exception as exc:
        value['analysis_notice'] = f'Musical estimates unavailable ({type(exc).__name__}); waveform and measurements remain available.'
    return value
