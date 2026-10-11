"""Exercise real uploads/decoding and API boundaries; substitute only expensive separation."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from app import store, main, worker
from app.audio import probe, profile
from app.config import STEMS

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(module, 'DATA', root) for module in (store, main, worker)]
        for p in self.patches: p.start()
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()
        self.audio = io.BytesIO()
        t = np.arange(44100 * 2) / 44100
        sf.write(self.audio, 0.15 * np.sin(2 * np.pi * 220 * t), 44100, format='WAV')

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        for p in self.patches: p.stop()
        self.temp.cleanup()

    def upload(self):
        return self.client.post('/api/projects', files={'file': ('tone.wav', self.audio.getvalue(), 'audio/wav')})

    def prepare(self):
        p = self.upload().json()
        def separated(source, output):
            output.mkdir(parents=True, exist_ok=True)
            samples, rate = sf.read(source)
            paths = {}
            for stem in STEMS:
                path = output / f'{stem}.wav'
                sf.write(path, samples / 6, rate)
                paths[stem] = path
            return paths
        with patch.object(worker, 'separate', separated), patch.object(worker, 'musical_analysis', profile):
            worker.process(store.claim())
        return p['id']

    def test_upload_rejects_empty_and_unsupported(self):
        self.assertEqual(self.client.post('/api/projects', files={'file': ('x.exe', b'bad')}).status_code, 400)
        self.assertEqual(self.client.post('/api/projects', files={'file': ('x.wav', b'')}).status_code, 400)
        self.assertEqual(self.client.get('/api/projects').json(), [])

    def test_job_claim_is_exclusive_and_failed_retry_is_guarded(self):
        project_id = self.upload().json()['id']
        self.assertIsNotNone(store.claim())
        self.assertIsNone(store.claim())
        self.assertEqual(self.client.post(f'/api/projects/{project_id}/retry').status_code, 409)
        store.update(project_id, status='failed', stage='failed', error='test')
        self.assertEqual(self.client.post(f'/api/projects/{project_id}/retry').status_code, 200)
        self.assertIsNotNone(store.claim())

    def test_complete_project_investigation_audio_and_export(self):
        project_id = self.prepare()
        info = self.client.get(f'/api/projects/{project_id}').json()
        self.assertEqual(info['status'], 'completed')
        self.assertEqual(info['stems'], list(STEMS))
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/audio/drums').status_code, 200)
        result = self.client.post(f'/api/projects/{project_id}/investigations', json={'stem':'drums', 'start':0.2, 'end':1.2})
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['status'], 'catalog_unavailable')
        self.assertEqual(result.json()['matches'], [])
        self.assertAlmostEqual(result.json()['profile']['duration'], 1, places=2)
        self.assertEqual(len(self.client.get(f'/api/projects/{project_id}').json()['investigations']), 1)
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/export').status_code, 200)

    def test_unknown_stems_and_invalid_passage_bounds(self):
        project_id = self.prepare()
        for selection in [ {'stem':'unknown','start':0,'end':1}, {'stem':'drums','start':-1,'end':1}, {'stem':'drums','start':1,'end':1}, {'stem':'drums','start':0,'end':3} ]:
            self.assertEqual(self.client.post(f'/api/projects/{project_id}/investigations', json=selection).status_code, 400)
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/audio/unknown').status_code, 404)
        self.assertEqual(self.client.get('/api/projects/not-a-project').status_code, 404)

    def test_missing_or_failed_results_not_published(self):
        project_id = self.upload().json()['id']
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/export').status_code, 409)
        store.update(project_id, status='failed', stage='failed')
        self.assertEqual(self.client.post(f'/api/projects/{project_id}/investigations', json={'stem':'drums','start':0,'end':1}).status_code, 409)

    def test_invalid_audio_fails_without_fake_stems(self):
        project_id = self.client.post('/api/projects', files={'file':('bad.wav',b'not audio')}).json()['id']
        worker.process(store.claim())
        self.assertEqual(store.get_project(project_id)['status'], 'failed')
        self.assertFalse((Path(self.temp.name)/project_id/'manifest.json').exists())

    def test_optional_jobs_are_deduplicated_and_project_scoped(self):
        project_id=self.prepare()
        self.assertIsNone(store.latest_job(project_id,'drums'))
        route=f'/api/projects/{project_id}/drums'
        first=self.client.post(route).json(); second=self.client.post(route).json()
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(store.claim_job()['id'],first['id'])
        self.assertIsNone(store.claim_job())
        other=self.upload().json()['id']
        self.assertEqual(self.client.get(f'/api/projects/{other}/jobs/{first["id"]}').status_code,404)
        store.finish_job(first['id'],error='controlled failure')
        self.assertEqual(store.get_project(project_id)['status'],'completed')
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/audio/drums').status_code,200)
        self.assertEqual(self.client.post(route).json()['status'],'queued')

    def test_render_limits_and_alignment(self):
        project_id=self.prepare(); route=f'/api/projects/{project_id}/renders'
        for settings in [{'tempo':0.1},{'tempo':2},{'semitones':13},{'semitones':1.5}]:
            self.assertIn(self.client.post(route,json=settings).status_code,(400,422))
        self.assertEqual(self.client.post(route,json={'expanded':True}).status_code,409)
        job=self.client.post(route,json={'tempo':1.25,'semitones':12}).json()
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/renders/{job["id"]}/vocals').status_code,409)
        worker.process_job(store.claim_job())
        self.assertEqual(store.get_job(job['id'])['status'],'completed')
        directory=Path(self.temp.name)/project_id/'renders'/job['id']
        sizes=[sf.info(directory/f'{stem}.wav').frames for stem in STEMS]
        self.assertEqual(set(sizes),{round(88200/1.25)})
        audio,rate=sf.read(directory/'vocals.wav'); mono=audio.mean(axis=1)
        spectrum=np.abs(np.fft.rfft(mono[rate//4:rate]))
        frequency=np.fft.rfftfreq(len(mono[rate//4:rate]),1/rate)[spectrum.argmax()]
        self.assertAlmostEqual(frequency,440,delta=5)
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/renders/{job["id"]}/download/zip').status_code,200)
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/renders/{job["id"]}/unknown').status_code,404)

    def test_drum_children_are_aligned_and_investigable(self):
        project_id=self.prepare()
        self.client.post(f'/api/projects/{project_id}/drums')
        def inference(*args,**kwargs):
            directory=Path(self.temp.name)/project_id
            samples,rate=sf.read(directory/'mix.wav')
            for name in ['kick','snare','hihat','toms','ride','crash']:
                sf.write(directory/'drum-components'/f'{name}.wav',samples/36,rate)
        with patch.object(worker.subprocess,'run',inference): worker.process_job(store.claim_job())
        info=self.client.get(f'/api/projects/{project_id}').json()
        self.assertEqual(len(info['drums']['files']),6)
        self.assertEqual(self.client.get(f'/api/projects/{project_id}/audio/kick').status_code,200)
        self.assertEqual(self.client.post(f'/api/projects/{project_id}/investigations',json={'stem':'kick','start':0,'end':1}).status_code,201)
        job=self.client.post(f'/api/projects/{project_id}/renders',json={'expanded':True}).json()
        worker.process_job(store.claim_job())
        stems=store.get_job(job['id'])['result']['stems']
        self.assertEqual(len(stems),11); self.assertNotIn('drums',stems)

    def test_chord_baseline_detects_known_triad_and_silence(self):
        from app.features import chord_sequence
        rate=22050; t=np.arange(rate*3)/rate
        triad=sum(np.sin(2*np.pi*f*t) for f in [261.63,329.63,392])/12
        source=Path(self.temp.name)/'chords.wav'
        sf.write(source,np.concatenate([triad,np.zeros(rate*2)]),rate)
        result=chord_sequence(source)
        self.assertTrue(result['estimated'])
        self.assertEqual(result['segments'][0]['chord'],'C')
        self.assertEqual(result['segments'][-1]['chord'],'N')

    def test_recognizer_upgrade_creates_job_and_refreshes_export(self):
        import zipfile
        project_id=self.prepare()
        old=store.enqueue(project_id,'analysis')
        store.finish_job(old['id'],result={})
        path=Path(self.temp.name)/project_id/'features.json'
        path.write_text(json.dumps({'chords':{'method':'baseline','segments':[]}}))
        first=self.client.get(f'/api/projects/{project_id}/export')
        with patch.object(main,'selected_method',return_value='chordino-nnls-v1'):
            job=self.client.post(f'/api/projects/{project_id}/analysis').json()
            again=self.client.post(f'/api/projects/{project_id}/analysis').json()
        self.assertNotEqual(old['id'],job['id'])
        self.assertEqual(job['id'],again['id'])
        self.assertEqual(job['payload']['method'],'chordino-nnls-v1')
        path.write_text(json.dumps({'chords':{'method':'chordino-nnls-v1','segments':[]}}))
        second=self.client.get(f'/api/projects/{project_id}/export')
        self.assertNotEqual(first.content,second.content)
        with zipfile.ZipFile(io.BytesIO(second.content)) as archive:
            self.assertEqual(json.loads(archive.read('features.json'))['chords']['method'],'chordino-nnls-v1')

    def test_misaligned_drum_results_are_not_published(self):
        project_id=self.prepare()
        queued=self.client.post(f'/api/projects/{project_id}/drums').json()
        def bad_inference(*args,**kwargs):
            directory=Path(self.temp.name)/project_id
            sf.write(directory/'drum-components'/'kick.wav',np.zeros((400,2)),44100)
        with patch.object(worker.subprocess,'run',bad_inference): worker.process_job(store.claim_job())
        self.assertEqual(store.get_job(queued['id'])['status'],'failed')
        self.assertIsNone(self.client.get(f'/api/projects/{project_id}').json()['drums'])
        self.assertEqual(store.get_project(project_id)['status'],'completed')

if __name__ == '__main__': unittest.main()
