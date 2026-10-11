import { test } from 'node:test';
import assert from 'node:assert/strict';
import { transposeChord } from '../src/music.ts';
test('transpose root and slash bass while keeping quality', () => {
  assert.equal(transposeChord('A/C#', 2), 'B/D#');
  assert.equal(transposeChord('Cmaj7/E', -1), 'Bmaj7/D#');
  assert.equal(transposeChord('Bbm7/Db', 2), 'Cm7/D#');
  assert.equal(transposeChord('E major', 1), 'F major');
  assert.equal(transposeChord('N', 4), 'N');
  assert.equal(transposeChord('G7', -12), 'G7');
});
