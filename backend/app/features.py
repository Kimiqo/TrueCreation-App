"""Local estimates and rendered listening copies; original audio stays immutable."""
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from .audio import profile
from . import chords

def chord_sequence(path):
    import librosa
    y, sr = librosa.load(path, sr=22050, mono=True)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=512)
    names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    templates = []
    labels = []
    for root in range(12):
        for suffix, third in [('',4),('m',3)]:
            template = np.zeros(12)
            template[[root,(root+third)%12,(root+7)%12]] = 1 / np.sqrt(3)
            templates.append(template); labels.append(names[root]+suffix)
    templates = np.array(templates)
    duration = len(y)/sr
    result = []
    for start in np.arange(0,duration,1.0):
        end = min(start+1,duration)
        a,b = int(start*sr/512), max(int(end*sr/512),int(start*sr/512)+1)
        vector = chroma[:,a:b].mean(axis=1)
        energy = float(np.sqrt(np.mean(y[int(start*sr):max(int(end*sr),int(start*sr)+1)]**2)))
        scores = templates @ (vector / max(np.linalg.norm(vector),1e-8))
        order = np.argsort(scores)
        best = int(order[-1]); score=float(scores[best]); margin=float(score-scores[order[-2]])
        label = labels[best] if energy>0.003 and score>=0.65 and margin>=0.015 else 'N'
        if result and result[-1]['chord']==label:
            result[-1]['end']=round(end,3)
        else:
            result.append({'start':round(float(start),3),'end':round(end,3),'chord':label})
    return {'method':'one-second-chroma-triad-baseline-v1','estimated':True,
            'notice':'Estimated major/minor triads; N means uncertain or silence. Extensions and inversions are not recognized.', 'segments':result}

def analyze(directory, info):
    waves = {name:profile(directory/relative)['waveform'] for name,relative in info['files'].items()}
    # Analyze the original mix: separated stems can omit harmonic content.
    # A broken installed recognizer fails the job visibly; only absence uses baseline.
    progression = chords.recognize(directory/'mix.wav') if chords.available() else chord_sequence(directory/'mix.wav')
    return {'waveforms':waves,'chords':progression}

def render(source: Path, target: Path, tempo: float, semitones: int):
    import librosa
    samples, rate = sf.read(source,dtype='float32',always_2d=True)
    transformed = samples.T
    if semitones:
        transformed = librosa.effects.pitch_shift(transformed,sr=rate,n_steps=semitones)
    if tempo != 1:
        transformed = librosa.effects.time_stretch(transformed,rate=tempo)
    # Exact common frame count keeps every stem on the same rendered timeline.
    frames = round(len(samples)/tempo)
    transformed = librosa.util.fix_length(transformed,size=frames,axis=-1)
    if not np.isfinite(transformed).all(): raise ValueError('Audio transform produced invalid samples')
    target.parent.mkdir(parents=True,exist_ok=True)
    sf.write(target,np.clip(transformed.T,-1,1),rate,subtype='PCM_16')

def write_json(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)); temporary.replace(path)
