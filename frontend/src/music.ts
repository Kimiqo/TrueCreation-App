const notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const flats: Record<string, string> = {Db:'C#', Eb:'D#', Gb:'F#', Ab:'G#', Bb:'A#', Cb:'B', Fb:'E'};
function shift(note: string, steps: number) {
  const index = notes.indexOf(flats[note] || note);
  return index < 0 ? note : notes[((index + steps) % 12 + 12) % 12];
}
export function transposeChord(chord: string, steps: number) {
  return chord.replace(/^([A-G](?:#|b)?)/, (_, note: string) => shift(note, steps))
    .replace(/\/([A-G](?:#|b)?)(?=$|[^a-zA-Z#b])/, (_, note: string) => '/' + shift(note, steps));
}
