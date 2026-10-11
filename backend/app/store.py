import json
import sqlite3
import time
from contextlib import contextmanager
from .config import DATA

@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'workspace.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL,
            status TEXT NOT NULL, stage TEXT NOT NULL, duration REAL,
            error TEXT, analysis TEXT, attempts INTEGER NOT NULL DEFAULT 0)''')
        db.execute('''CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            created REAL NOT NULL, result TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
            payload TEXT NOT NULL, created REAL NOT NULL, status TEXT NOT NULL,
            error TEXT, result TEXT, UNIQUE(project_id,kind,payload))''')

def project(row):
    value = dict(row)
    value['analysis'] = json.loads(value['analysis']) if value['analysis'] else None
    return value

def list_projects():
    with connect() as db:
        return [project(r) for r in db.execute('SELECT * FROM projects ORDER BY created DESC')]

def get_project(project_id):
    with connect() as db:
        row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        return project(row) if row else None

def update(project_id, **fields):
    permitted = {'status', 'stage', 'duration', 'error', 'analysis'}
    assert fields and set(fields) <= permitted
    if 'analysis' in fields:
        fields['analysis'] = json.dumps(fields['analysis'])
    with connect() as db:
        db.execute('UPDATE projects SET ' + ','.join(f'{k}=?' for k in fields) + ' WHERE id=?', (*fields.values(), project_id))

def claim():
    # Single worker process in local development. Short claim transaction only.
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM projects WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row:
            return None
        db.execute("UPDATE projects SET status='processing', stage='validating', attempts=attempts+1 WHERE id=?", (row['id'],))
        return project(row)

def create(project_id, title):
    with connect() as db:
        db.execute("INSERT INTO projects(id,title,created,status,stage) VALUES(?,?,?,'queued','queued')", (project_id, title, time.time()))

def job(row):
    if row is None: return None
    value = dict(row)
    value['payload'] = json.loads(value['payload'])
    value['result'] = json.loads(value['result']) if value['result'] else None
    return value

def enqueue(project_id, kind, payload=None):
    import uuid
    encoded = json.dumps(payload or {}, sort_keys=True)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("INSERT OR IGNORE INTO jobs(id,project_id,kind,payload,created,status) VALUES(?,?,?,?,?,'queued')", (uuid.uuid4().hex, project_id, kind, encoded, time.time()))
        db.execute("UPDATE jobs SET status='queued',error=NULL WHERE project_id=? AND kind=? AND payload=? AND status='failed'", (project_id, kind, encoded))
        return job(db.execute('SELECT * FROM jobs WHERE project_id=? AND kind=? AND payload=?', (project_id, kind, encoded)).fetchone())

def get_job(job_id):
    with connect() as db:
        return job(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

def latest_job(project_id, kind):
    with connect() as db:
        return job(db.execute('SELECT * FROM jobs WHERE project_id=? AND kind=? ORDER BY created DESC LIMIT 1', (project_id,kind)).fetchone())

def claim_job():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if row is None: return None
        db.execute("UPDATE jobs SET status='processing' WHERE id=?", (row['id'],))
        return job(row)

def finish_job(job_id, result=None, error=None):
    with connect() as db:
        db.execute('UPDATE jobs SET status=?,result=?,error=? WHERE id=?', ('failed' if error else 'completed', json.dumps(result) if result else None, error, job_id))
