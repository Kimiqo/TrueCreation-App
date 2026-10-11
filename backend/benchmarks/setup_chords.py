"""Fetch pinned benchmark inputs only with --download, then build the local host.
No global installations. Requires a C++ compiler and existing Boost headers.
"""
import argparse,hashlib,json,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'data/chord-benchmark/tools'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');args=parser.parse_args()
 manifest=json.loads((Path(__file__).parent/'downloads.json').read_text())
 print('Source and checkpoint payload:',sum(f['size'] for s in manifest for f in s['files']),'bytes')
 for spec in manifest:
  for item in spec['files']:
   path=TOOLS/spec['name']/item['path']
   if not path.exists():
    if not args.download:raise SystemExit('Missing '+str(path)+'; review sizes and run with --download.')
    path.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(item['url'],timeout=60) as response:path.write_bytes(response.read())
   if path.stat().st_size!=item['size']:raise SystemExit('Size mismatch: '+str(path))
   if item.get('sha256') and hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Digest mismatch: '+str(path))
 sdk=TOOLS/'vamp';src=TOOLS/'chordino'
 cmd=['c++','-std=c++11','-O2','-I'+str(src),'-I'+str(sdk),'-I/opt/homebrew/include',str(Path(__file__).parent/'chordino_host.cpp')]
 cmd += [str(src/f) for f in ['Chordino.cpp','NNLSBase.cpp','chromamethods.cpp','nnls.c','viterbi.cpp']]
 cmd += [str(sdk/'src/vamp-sdk'/f) for f in ['FFT.cpp','RealTime.cpp']]
 subprocess.run(cmd+['-o',str(TOOLS/'chordino-host')],check=True)
 print('Built',TOOLS/'chordino-host')
if __name__=='__main__':main()
