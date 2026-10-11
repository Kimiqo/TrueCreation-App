import os
from pathlib import Path

DATA = Path(os.environ.get('TRUECREATION_DATA', Path(__file__).resolve().parents[1] / 'data')).resolve()
MODEL = 'htdemucs_6s'
STEMS = ('vocals', 'drums', 'bass', 'guitar', 'piano', 'other')
MAX_BYTES = 75 * 1024 * 1024
MAX_SECONDS = 180
