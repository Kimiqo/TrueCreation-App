"""Isolated, pinned MDX23C inference. Run as a subprocess to release model memory."""
import hashlib
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from .config import DATA

VENDOR=Path(__file__).resolve().parents[1]/'vendor'/'mdxnet-infer'/'src'
sys.path.insert(0,str(VENDOR))
from mdxnet_infer import MDX23CInference

class SafeInference(MDX23CInference):
    def _load_weights(self,path):
        value=torch.load(path,map_location='cpu',weights_only=True)
        if 'state_dict' in value: value=value['state_dict']
        elif 'model_state_dict' in value: value=value['model_state_dict']
        self.model.load_state_dict(value)

def run(source, output):
    torch.set_num_threads(4)
    cache=DATA/'model-cache'/'mdx23c'
    metadata=MDX23CInference.KNOWN_MODELS['drumsep-6stem']
    # Never start an implicit network download in a worker.
    for kind in ('ckpt','yaml'):
        path=cache/metadata[f'{kind}_url'].split('/')[-1]
        if not path.exists(): raise ValueError('MDX23C weights are not cached. Follow the model setup instructions.')
        with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=metadata[f'{kind}_sha256']:
            raise ValueError(f'MDX23C {kind} checksum mismatch')
    engine=SafeInference.from_pretrained('drumsep-6stem',cache_dir=cache,device='cpu')
    samples,rate=sf.read(source,dtype='float32',always_2d=True)
    parts=engine.separate(samples,sample_rate=rate,progress=True)
    output.mkdir(parents=True,exist_ok=True)
    for name,audio in parts.items():
        name='hihat' if name=='hh' else name
        if audio.shape != samples.shape or not np.isfinite(audio).all():
            raise ValueError('Drum output does not match the source timeline')
        sf.write(output/f'{name}.wav',np.clip(audio,-1,1),rate,subtype='PCM_16')

if __name__=='__main__': run(Path(sys.argv[1]),Path(sys.argv[2]))
