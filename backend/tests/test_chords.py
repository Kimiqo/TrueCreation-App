import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import chords, features

class ChordTests(unittest.TestCase):
    def test_events_cover_timeline_and_preserve_extensions_and_inversions(self):
        output = '0.2\tCmaj7/E\n1.0\tAm7\n1.0\tAm7/G\n2.0\tAm7/G\n3.5\tN\n4.0\tN\n'
        self.assertEqual(chords.parse_segments(output, 4), [
            {'start':0,'end':0.2,'chord':'N'},
            {'start':0.2,'end':1.0,'chord':'Cmaj7/E'},
            {'start':1.0,'end':3.5,'chord':'Am7/G'},
            {'start':3.5,'end':4,'chord':'N'}])

    def test_invalid_host_output_is_not_published_as_silence(self):
        for output in ['', 'nan\tC', '1\tC\n0.5\tG', 'bad output']:
            with self.subTest(output=output), self.assertRaises(ValueError):
                chords.parse_segments(output, 4)

    def test_missing_host_falls_back_but_broken_installed_host_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            info={'files':{}}
            baseline={'method':chords.BASELINE}
            with patch.object(chords,'available',return_value=False), patch.object(features,'chord_sequence',return_value=baseline):
                self.assertEqual(features.analyze(root,info)['chords'],baseline)
            with patch.object(chords,'available',return_value=True), patch.object(chords,'recognize',side_effect=RuntimeError('host failed')):
                with self.assertRaisesRegex(RuntimeError,'host failed'): features.analyze(root,info)
