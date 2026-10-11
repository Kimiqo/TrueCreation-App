"""Controlled synthetic benchmark, not a real-music accuracy claim. Run from backend."""
import sys,json,time,subprocess,re,types,hashlib
from pathlib import Path
import numpy as np,librosa,soundfile as sf,torch,yaml
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.features import chord_sequence
CACHE=ROOT/'data/chord-benchmark';TOOLS=CACHE/'tools';SR=22050
NAMES=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
QUAL=['min','maj','dim','aug','min6','maj6','min7','minmaj7','maj7','7','dim7','hdim7','sus2','sus4']
def canonical(label):
 if label in ['N','X','']:return 'N'
 m=re.match(r'^([A-G](?:#|b)?)(.*)$',label)
 if not m:return label
 root,suffix=m.groups();root={'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}.get(root,root)
 suffix=suffix.removeprefix(':');suffix={'':'maj','m':'min','M':'maj','m7':'min7','m6':'min6'}.get(suffix,suffix)
 return root+':'+suffix

def chordino(path):
 y,sr=librosa.load(path,sr=SR,mono=True);raw=CACHE/'input.f32';y.astype('float32').tofile(raw)
 r=subprocess.run([str(TOOLS/'chordino-host'),str(raw),str(sr)],capture_output=True,text=True,check=True)
 events=[]
 for line in r.stdout.splitlines():
  stamp,label=line.split('\t',1);stamp=max(0,min(len(y)/sr,float(stamp)))
  if stamp<len(y)/sr:events.append((stamp,canonical(label)))
 if not events:raise RuntimeError('Chordino returned no labels; check host lifecycle before scoring')
 if events[0][0]>0:events.insert(0,(0,'N'))
 return [{'start':a,'end':events[i+1][0] if i+1<len(events) else len(y)/sr,'chord':b} for i,(a,b) in enumerate(events)]

class BTC:
 def __init__(self):
  directory=TOOLS/'btc';sys.path.insert(0,str(directory));source=directory/'utils/transformer_modules.py'
  module=types.ModuleType('utils.transformer_modules');module.__file__=str(source);sys.modules['utils.transformer_modules']=module
  # Removed NumPy alias: compatibility patch in memory, original source preserved.
  exec(compile(source.read_text().replace('astype(np.float)','astype(float)'),str(source),'exec'),module.__dict__)
  from btc_model import BTC_model
  self.config=yaml.safe_load((directory/'run_config.yaml').read_text());self.config['model']['num_chords']=170
  torch.set_num_threads(4)
  with torch.serialization.safe_globals([(np._core.multiarray.scalar,'numpy.core.multiarray.scalar'),np.dtype,type(np.dtype('float32')),type(np.dtype('float64'))]):
   c=torch.load(directory/'test/btc_model_large_voca.pt',map_location='cpu',weights_only=True)
  self.model=BTC_model(self.config['model']);self.model.load_state_dict(c['model']);self.model.eval();self.mean=float(c['mean']);self.std=float(c['std'])
 def __call__(self,path):
  y,sr=librosa.load(path,sr=SR,mono=True);cfg=self.config['feature'];chunk=SR*10
  f=np.concatenate([librosa.cqt(y[a:a+chunk],sr=sr,n_bins=cfg['n_bins'],bins_per_octave=cfg['bins_per_octave'],hop_length=cfg['hop_length']) for a in range(0,len(y),chunk)],axis=1)
  f=np.log(np.abs(f)+1e-6).T;f=(f-self.mean)/self.std
  count=len(f);window=self.config['model']['timestep'];f=np.pad(f,((0,(-count)%window),(0,0)));pred=[]
  with torch.inference_mode():
   for a in range(0,len(f),window):
    output,_=self.model.self_attn_layers(torch.tensor(f[a:a+window],dtype=torch.float32).unsqueeze(0));p,_=self.model.output_layer(output);pred.extend(p.reshape(-1).tolist())
  result=[];step=self.config['mp3']['inst_len']/self.config['model']['timestep'];duration=len(y)/sr
  for i,p in enumerate(pred[:count]):
   if i*step>=duration:break
   name=NAMES[int(p)//14]+':'+QUAL[int(p)%14] if int(p)<168 else 'N'
   end=min((i+1)*step,duration)
   if result and result[-1]['chord']==name:result[-1]['end']=end
   else:result.append({'start':i*step,'end':end,'chord':name})
  return result

def make_case(name,chords,seconds=2.5,kind='harmonic'):
 rng=np.random.default_rng(731);parts=[];truth=[];start=0
 intervals={'maj':[0,4,7],'min':[0,3,7],'7':[0,4,7,10],'min7':[0,3,7,10],'maj7':[0,4,7,11],'sus4':[0,5,7]}
 for root,quality in chords:
  t=np.arange(round(seconds*SR))/SR;y=np.zeros(len(t));label='N' if root is None else NAMES[root]+':'+quality
  if root is not None:
   for k,note in enumerate(intervals[quality]):
    frequency=440*2**((48+root+note-69)/12)
    for h in range(1,6):y+=np.sin(2*np.pi*frequency*h*t)/(h**1.5)*(1 if k else 1.2)
   envelope=np.minimum(t/.03,1)*np.minimum((seconds-t)/.05,1)
   if kind=='rhythmic':envelope*=.25+.75*np.exp(-5*(t%.5))
   y*=envelope*.06
  if kind=='rhythmic':y+=rng.normal(0,.015,len(t))*np.exp(-35*(t%.5))
  if kind=='noise':y=rng.normal(0,.018,len(t))*np.exp(-40*(t%.5))
  parts.append(y);truth.append({'start':start,'end':start+len(t)/SR,'chord':label});start+=len(t)/SR
 path=CACHE/(name+'.wav');sf.write(path,np.concatenate(parts),SR);return name,path,truth

def at(sequence,t):return next((x['chord'] for x in sequence if x['start']<=t<x['end']),'N')
def score(estimate,truth):
 times=np.arange(.025,truth[-1]['end'],.05);actual=[at(truth,t) for t in times];pred=[at(estimate,t) for t in times]
 def reduce(c):
  if c=='N':return c
  root,q=c.split(':',1);return root+':'+('min' if q.startswith('min') else 'maj' if q in ['maj','7','maj7','maj6'] else q)
 return {'exact_label_pct':round(np.mean([a==p for a,p in zip(actual,pred)])*100,2),'major_minor_reduction_pct':round(np.mean([reduce(a)==reduce(p) for a,p in zip(actual,pred)])*100,2),'unknown_pct':round(np.mean([p=='N' for p in pred])*100,2)}

def main():
 cases=[make_case('all-roots-triads',[(r,q) for r in range(12) for q in ['maj','min']]),make_case('rhythmic-progression',[(0,'maj'),(7,'maj'),(9,'min'),(5,'maj')]*2,3,'rhythmic'),make_case('extended-chords',[(0,'maj7'),(2,'min7'),(7,'7'),(0,'maj'),(9,'min7'),(5,'maj7'),(7,'sus4'),(0,'maj')],3),make_case('silence',[(None,'')]*4,2),make_case('percussion-only',[(None,'')]*4,2,'noise')]
 t=time.perf_counter();btc=BTC();print('BTC load',round(time.perf_counter()-t,3),'s',flush=True)
 engines={'baseline':lambda p:[{**s,'chord':canonical(s['chord'])} for s in chord_sequence(p)['segments']],'chordino':chordino,'btc-large':btc}
 # Warm feature compilation once before reporting measured runs.
 engines['baseline'](cases[0][1]);btc(cases[0][1]);results=[]
 for name,path,truth in cases:
  for method,run in engines.items():
   t=time.perf_counter();output=run(path);row={'case':name,'method':method,'seconds':round(time.perf_counter()-t,3),'segments':len(output),**score(output,truth)};results.append(row);print(json.dumps(row),flush=True)
 real=ROOT/'data/051f78c9e60540c1a537520249743689/mix.wav'
 if real.exists():
  for method,run in engines.items():
   t=time.perf_counter();output=run(real);row={'case':'uploaded-song-unlabelled','method':method,'seconds':round(time.perf_counter()-t,3),'segments':len(output),'accuracy':None};results.append(row);(CACHE/(method+'-real.json')).write_text(json.dumps(output));print(json.dumps(row),flush=True)
 provenance=json.loads((Path(__file__).parent/'downloads.json').read_text())
 for spec in provenance:
  for f in spec['files']:f['sha256']=hashlib.sha256((TOOLS/spec['name']/f['path']).read_bytes()).hexdigest()
 report={'limitations':'Synthetic accuracy only. Uploaded song has no ground truth. Single warm CPU run per case; not a rigorous runtime distribution.','sample_rate':SR,'thread_count':4,'results':results,'downloads':provenance}
 (CACHE/'results.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
