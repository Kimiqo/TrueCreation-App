import json
import hashlib
import math
import shutil
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import store
from .audio import profile
from .config import DATA, MAX_BYTES, MAX_SECONDS, MODEL, STEMS
from .separation import available
from .chords import selected_method

@asynccontextmanager
async def lifespan(app):
    store.initialize()
    yield

app = FastAPI(title='TrueCreation local workspace', lifespan=lifespan)

def required(project_id):
    result = store.get_project(project_id)
    if not result:
        raise HTTPException(404, 'Project not found')
    return result

def manifest(project_id):
    if required(project_id)['status'] != 'completed':
        raise HTTPException(409, 'Stems are not ready yet')
    path = DATA / project_id / 'manifest.json'
    if not path.exists():
        raise HTTPException(409, 'Stems are not ready yet')
    return json.loads(path.read_text())

@app.get('/api/health')
def health():
    drum_cached = len(list((DATA/'model-cache'/'mdx23c').glob('*.ckpt')))>0
    return {'mode': 'local-single-user', 'separation_installed': available(), 'model': MODEL, 'chord_method': selected_method(),
            'stems': list(STEMS), 'drum_expansion': 'local_evaluation' if drum_cached else 'weights_missing', 'catalog': 'unavailable',
            'ffmpeg': bool(shutil.which('ffmpeg')), 'max_seconds': MAX_SECONDS, 'max_bytes': MAX_BYTES}

@app.get('/api/projects')
def projects():
    return store.list_projects()

@app.post('/api/projects', status_code=201)
async def upload(file: UploadFile = File()):
    if Path(file.filename or '').suffix.lower() not in {'.wav', '.mp3'}:
        raise HTTPException(400, 'Upload a WAV or MP3 file')
    project_id = uuid.uuid4().hex
    directory = DATA / project_id
    directory.mkdir(parents=True)
    size = 0
    try:
        with (directory / 'source').open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'File exceeds the 75 MB local MVP limit')
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, 'The uploaded file is empty')
        store.create(project_id, Path(file.filename).name)
    except Exception:
        shutil.rmtree(directory)
        raise
    finally:
        await file.close()
    return required(project_id)

@app.get('/api/projects/{project_id}')
def detail(project_id: str):
    result = required(project_id)
    result['stems'] = manifest(project_id)['stems'] if result['status'] == 'completed' else []
    directory = DATA/project_id
    result['features'] = json.loads((directory/'features.json').read_text()) if (directory/'features.json').exists() else None
    result['drum_job'] = store.latest_job(project_id,'drums')
    result['analysis_job'] = store.latest_job(project_id,'analysis')
    result['drums'] = json.loads((directory/'drums.json').read_text()) if (directory/'drums.json').exists() else None
    with store.connect() as db:
        result['investigations'] = [json.loads(row['result']) for row in db.execute('SELECT result FROM investigations WHERE project_id=? ORDER BY created DESC', (project_id,))]
    return result

@app.post('/api/projects/{project_id}/retry')
def retry(project_id: str):
    required(project_id)
    with store.connect() as db:
        count = db.execute("UPDATE projects SET status='queued',stage='queued',error=NULL WHERE id=? AND status='failed'", (project_id,)).rowcount
    if not count:
        raise HTTPException(409, 'Only failed projects can be retried')
    return required(project_id)

@app.get('/api/projects/{project_id}/audio/{stem}')
def audio(project_id: str, stem: str):
    required(project_id)
    if stem == 'mix':
        path = DATA / project_id / 'mix.wav'
    else:
        files = audio_files(project_id)
        if stem not in files: raise HTTPException(404, 'Unknown stem')
        path = DATA/project_id/files[stem]
    if not path.is_file():
        raise HTTPException(409, 'Audio is not ready')
    return FileResponse(path, media_type='audio/wav', filename=f'{stem}.wav')

class Investigation(BaseModel):
    stem: str
    start: float
    end: float

@app.post('/api/projects/{project_id}/investigations', status_code=201)
def investigate(project_id: str, selection: Investigation):
    info = manifest(project_id)
    files = audio_files(project_id)
    if selection.stem not in (*files, 'mix'):
        raise HTTPException(400, 'Unknown stem')
    if not all(math.isfinite(v) for v in (selection.start, selection.end)) or not 0 <= selection.start < selection.end <= info['duration'] or selection.end-selection.start > 30:
        raise HTTPException(400, 'Select a valid passage up to 30 seconds long')
    path = DATA / project_id / ('mix.wav' if selection.stem == 'mix' else files[selection.stem])
    result = {'id': uuid.uuid4().hex, **selection.model_dump(), 'profile': profile(path, selection.start, selection.end),
              'status': 'catalog_unavailable', 'matches': [], 'message': 'Passage analyzed. No reference catalog is connected, so source identification is unavailable.'}
    with store.connect() as db:
        db.execute('INSERT INTO investigations VALUES(?,?,?,?)', (result['id'], project_id, time.time(), json.dumps(result)))
    return result

@app.get('/api/projects/{project_id}/export')
def export(project_id: str):
    info = manifest(project_id)
    files = audio_files(project_id)
    info = {**info,'files':files,'stems':list(files)}
    directory = DATA / project_id
    features = (directory/'features.json').read_bytes() if (directory/'features.json').exists() else None
    revision = hashlib.sha256(features).hexdigest()[:16] if features is not None else 'none'
    prefix = 'expanded' if (directory/'drums.json').exists() else 'base'
    target = directory / f'{prefix}-stems-v3-{revision}.zip'
    if not target.exists():
        # Unique temporary paths avoid concurrent export writers clobbering one another.
        temp = directory / f'export-{uuid.uuid4().hex}.tmp'
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
            for stem, relative in info['files'].items():
                archive.write(directory / relative, f'{stem}.wav')
            archive.writestr('analysis.json', json.dumps(info, indent=2))
            if features is not None: archive.writestr('features.json', features)
        temp.replace(target)
    return FileResponse(target, media_type='application/zip', filename='truecreation-stems.zip')

def audio_files(project_id):
    files = dict(manifest(project_id)['files'])
    path = DATA/project_id/'drums.json'
    if path.exists(): files.update(json.loads(path.read_text())['files'])
    return files

@app.post('/api/projects/{project_id}/analysis')
def analyze_project(project_id: str):
    manifest(project_id)
    return store.enqueue(project_id,'analysis',{'method':selected_method()})

@app.post('/api/projects/{project_id}/drums')
def expand_drums(project_id: str):
    manifest(project_id)
    return store.enqueue(project_id,'drums')

class RenderRequest(BaseModel):
    tempo: float = 1
    semitones: int = 0
    expanded: bool = False

@app.post('/api/projects/{project_id}/renders')
def render_project(project_id: str, settings: RenderRequest):
    manifest(project_id)
    if not math.isfinite(settings.tempo) or not 0.5<=settings.tempo<=1.5 or not -12<=settings.semitones<=12:
        raise HTTPException(400,'Use tempo 50–150% and transpose −12 to +12 semitones')
    if settings.expanded and not (DATA/project_id/'drums.json').exists():
        raise HTTPException(409,'Drum components are not ready')
    return store.enqueue(project_id,'render',settings.model_dump())

@app.get('/api/projects/{project_id}/jobs/{job_id}')
def get_job(project_id: str, job_id: str):
    required(project_id)
    value=store.get_job(job_id)
    if not value or value['project_id']!=project_id: raise HTTPException(404,'Job not found')
    return value

@app.get('/api/projects/{project_id}/renders/{job_id}/{stem}')
def rendered_audio(project_id: str, job_id: str, stem: str):
    job=get_job(project_id,job_id)
    if job['kind']!='render' or job['status']!='completed': raise HTTPException(409,'Rendered audio not ready')
    if stem not in job['result']['stems']: raise HTTPException(404,'Unknown stem')
    return FileResponse(DATA/project_id/'renders'/job_id/f'{stem}.wav',media_type='audio/wav',filename=f'{stem}.wav')

@app.get('/api/projects/{project_id}/renders/{job_id}/download/zip')
def rendered_export(project_id: str, job_id: str):
    job=get_job(project_id,job_id)
    if job['kind']!='render' or job['status']!='completed': raise HTTPException(409,'Rendered audio not ready')
    directory=DATA/project_id/'renders'/job_id
    target=directory/'rendered.zip'
    if not target.exists():
        temporary=directory/f'{uuid.uuid4().hex}.tmp'
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            for name in job['result']['stems']: archive.write(directory/f'{name}.wav',f'{name}.wav')
            archive.writestr('settings.json',json.dumps(job['result'],indent=2))
        temporary.replace(target)
    return FileResponse(target,media_type='application/zip',filename='truecreation-listening-version.zip')
