"""Invoke the separately built Chordino CLI; never download models at runtime."""
import math
import os
import subprocess
import tempfile
from pathlib import Path
from .config import DATA

METHOD = 'chordino-nnls-v1'
BASELINE = 'one-second-chroma-triad-baseline-v1'

def executable():
    return Path(os.environ.get('TRUECREATION_CHORDINO', DATA/'chord-benchmark/tools/chordino-host'))

def available():
    host = executable()
    return host.is_file() and os.access(host, os.X_OK)

def selected_method():
    return METHOD if available() else BASELINE

def parse_segments(output, duration):
    events = []
    for line in output.splitlines():
        stamp, label = line.split('\t', 1)
        stamp = float(stamp)
        if not math.isfinite(stamp): raise ValueError('Invalid Chordino timestamp')
        stamp = round(max(0, min(duration, stamp)), 3)
        if stamp >= duration: continue
        label = label.strip() or 'N'
        if events and stamp < events[-1][0]: raise ValueError('Unordered Chordino timestamps')
        if events and stamp == events[-1][0]: events[-1] = (stamp, label)
        else: events.append((stamp, label))
    if not events: raise ValueError('Chordino returned no chord labels')
    if events[0][0] > 0: events.insert(0, (0, 'N'))
    segments = []
    for i, (start, label) in enumerate(events):
        end = events[i+1][0] if i+1 < len(events) else round(duration, 3)
        if end <= start: continue
        if segments and segments[-1]['chord'] == label: segments[-1]['end'] = end
        else: segments.append({'start': start, 'end': end, 'chord': label})
    return segments

def recognize(path):
    import librosa
    y, sr = librosa.load(path, sr=22050, mono=True)
    # Private temporary inputs allow concurrent calls without clobbering another song.
    with tempfile.TemporaryDirectory(prefix='truecreation-chords-') as directory:
        raw = Path(directory)/'input.f32'
        y.astype('float32').tofile(raw)
        result = subprocess.run([str(executable()), str(raw), str(sr)],
                                capture_output=True, text=True, check=True, timeout=120)
    return {'method': METHOD, 'estimated': True,
            'notice': 'Chordino estimates chord changes, including sevenths and inversions. N means no recognized chord or silence. Dense mixes can produce incorrect labels; these are not verified transcriptions.',
            'segments': parse_segments(result.stdout, len(y)/sr)}
