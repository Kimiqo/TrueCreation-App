import json
import fcntl
import time
import traceback
import subprocess
import sys
from . import store
from .audio import probe, decode, musical_analysis
from .config import DATA, MODEL, STEMS
from .separation import separate
from .features import analyze, render, write_json

def process(project):
    project_id = project['id']
    directory = DATA / project_id
    try:
        duration = probe(directory / 'source')
        store.update(project_id, duration=duration)
        decode(directory / 'source', directory / 'mix.wav')
        store.update(project_id, stage='analyzing')
        analysis = musical_analysis(directory / 'mix.wav')
        store.update(project_id, analysis=analysis, stage='separating')
        paths = separate(directory / 'mix.wav', directory / 'separated')
        manifest = {'model': MODEL, 'stems': list(STEMS), 'duration': duration, 'analysis': analysis,
                    'files': {name: str(path.relative_to(directory)) for name,path in paths.items()}}
        target = directory / 'manifest.json'
        temporary = directory / 'manifest.tmp'
        temporary.write_text(json.dumps(manifest, indent=2))
        temporary.replace(target)
        store.update(project_id, status='completed', stage='ready', error=None)
    except Exception as exc:
        traceback.print_exc()
        store.update(project_id, status='failed', stage='failed', error=str(exc)[:1000])

def main():
    store.initialize()
    lock = (DATA / 'worker.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('A local audio worker is already running. Stop it before starting another.')
    # The local worker is single-process; starting a replacement recovers interrupted work.
    with store.connect() as db:
        db.execute("UPDATE projects SET status='queued', stage='queued' WHERE status='processing'")
        db.execute("UPDATE jobs SET status='queued' WHERE status='processing'")
    print('TrueCreation worker ready. Local CPU inference; one job at a time.', flush=True)
    while True:
        task = store.claim()
        if task:
            process(task)
        else:
            extra = store.claim_job()
            if extra: process_job(extra)
            else: time.sleep(1)

def process_job(job):
    directory=DATA/job['project_id']
    try:
        info=json.loads((directory/'manifest.json').read_text())
        if job['kind']=='analysis':
            result=analyze(directory,info)
            write_json(directory/'features.json',result)
        elif job['kind']=='drums':
            output=directory/'drum-components'
            output.mkdir(exist_ok=True)
            with (output/'inference.log').open('w') as log:
                try:
                    subprocess.run([sys.executable,'-m','app.drum_infer',str(directory/info['files']['drums']),str(output)],stdout=log,stderr=log,check=True,timeout=3600)
                except subprocess.CalledProcessError as exc:
                    raise ValueError((output/'inference.log').read_text(errors='replace')[-1200:]) from exc
            names=['kick','snare','hihat','toms','ride','crash']
            result={'model':'mdx23c-drumsep-6stem-v0.1.0','license':'unresolved-local-evaluation','files':{},'waveforms':{}}
            import soundfile as sf
            from .audio import profile
            parent=sf.info(directory/info['files']['drums'])
            for name in names:
                path=output/f'{name}.wav'; value=sf.info(path)
                if value.frames!=parent.frames or value.samplerate!=parent.samplerate or value.channels!=2:
                    raise ValueError('Drum output is not aligned stereo audio')
                result['files'][name]=str(path.relative_to(directory))
                result['waveforms'][name]=profile(path)['waveform']
            write_json(directory/'drums.json',result)
        elif job['kind']=='render':
            payload=job['payload']; files=dict(info['files'])
            if payload['expanded']:
                drum=json.loads((directory/'drums.json').read_text())
                files.pop('drums'); files.update(drum['files'])
            output=directory/'renders'/job['id']
            for name,relative in files.items():
                render(directory/relative,output/f'{name}.wav',payload['tempo'],payload['semitones'])
            result={'stems':list(files),'duration':info['duration']/payload['tempo'],**payload}
        else: raise ValueError('Unknown background task')
        store.finish_job(job['id'],result=result)
    except Exception as exc:
        traceback.print_exc(); store.finish_job(job['id'],error=str(exc)[:1500])

if __name__ == '__main__':
    main()
