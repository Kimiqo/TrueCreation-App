import { useEffect, useRef } from 'react';

type Chord = { start: number; end: number; chord: string };
const time = (seconds: number) => `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
const label = (chord: string) => chord === 'N' || chord === 'X' ? 'Uncertain' : chord;

export function ChordProgression({segments, position, loaded, transpose, seek}: {
  segments: Chord[]; position: number; loaded: boolean;
  transpose: (chord: string) => string; seek: (seconds: number) => void;
}) {
  const index = segments.findIndex(chord => position >= chord.start && position < chord.end);
  const current = segments[index], next = index >= 0 ? segments[index + 1] : undefined;
  const rail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const container = rail.current, card = container?.children[index] as HTMLElement | undefined;
    if (container && card) container.scrollTo({left: Math.max(0, card.offsetLeft - container.offsetLeft - 20), behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }, [index]);
  if (!segments.length) return <p>Chord estimates appear when analysis finishes.</p>;
  return <>
    <div className="chord-now"><div><small>PLAYING NOW · ESTIMATE</small><strong>{current ? label(transpose(current.chord)) : '—'}</strong><span>{current ? `${time(current.start)}–${time(current.end)}` : 'Select a moment'}</span></div><div><small>UP NEXT</small><strong>{next ? label(transpose(next.chord)) : '—'}</strong><span>{next ? `at ${time(next.start)}` : 'End of sequence'}</span></div></div>
    <div className="chord-legend"><span className="major">Major / other</span><span className="minor">Minor</span><span className="unknown">Uncertain / silence</span></div>
    <div className="chord-rail" ref={rail} aria-label="Chord sequence">
      {segments.map((chord, i) => {
        const name = transpose(chord.chord), unknown = ['N', 'X'].includes(name);
        const progress = Math.max(0, Math.min(100, (position - chord.start) / (chord.end - chord.start) * 100));
        return <button key={`${i}/${chord.start}`} disabled={!loaded} aria-current={i === index ? 'true' : undefined} aria-label={`Seek to ${label(name)} at ${chord.start} seconds`} title={`${label(name)} · ${chord.start.toFixed(1)}–${chord.end.toFixed(1)} seconds`} className={`chord-card ${unknown ? 'unknown' : /^[A-G][#b]?m(?!aj)/.test(name) ? 'minor' : 'major'} ${i === index ? 'current' : ''}`} onClick={() => seek(chord.start)}>
          <small>{time(chord.start)}</small><strong>{label(name)}</strong><span>{(chord.end - chord.start).toFixed(1)} s</span><div className="chord-progress"><i style={{width: `${progress}%`}}/></div>
        </button>;
      })}
    </div>
    <p className="footnote">Scroll through the sequence. Click a chord to seek after loading audio. Cards show durations; their widths are equal.</p>
  </>;
}
