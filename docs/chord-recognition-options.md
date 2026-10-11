# Chord recognition upgrade candidates

Initial assessment checked 11 October 2026. Subsequently benchmarked and integrated Chordino following the user’s selection; see [results and limitations](chord-benchmark.md). BTC stays a comparison option.

The retained fallback recognizer averages chroma into one-second windows and compares major/minor templates. It does not model neighboring chords, extensions, or inversions. Changing the UI or using a GPU does not by itself improve recognition accuracy.

## Chordino: practical first benchmark

[Official description](https://isophonics.net/nnls-chroma). Chordino uses NNLS chroma, a configurable chord dictionary and HMM/Viterbi temporal smoothing. This gives a more developed candidate than our fixed-window baseline, but its authors explicitly describe it as non-state-of-the-art. It is a conventional signal-processing plugin, with no trained checkpoint required. It needs a Vamp host/plugin integration; platform packaging and GPL obligations should be assessed for the selected deployment.

Recommendation: benchmark Chordino first for a low-cost, CPU-based improvement path. Compare the original mix and a recombined accompaniment excluding vocals/drums; separation may help or introduce artifacts, so accompaniment input is a hypothesis, not guaranteed to be better. Keep unknown/no-chord regions rather than forcing labels.

## BTC: neural candidate

[Official source](https://github.com/jayg996/BTC-ISMIR19), [paper](https://arxiv.org/abs/1907.02698). The bidirectional transformer uses musical context and supports major/minor or a larger chord vocabulary. Code is MIT; verify the specific pretrained checkpoint's terms and provenance separately. Existing PyTorch can support integration, but required inference dependencies and checkpoint compatibility must be checked before installation. Do not assume every training dependency is needed for serving.

[ChordMini](https://github.com/ptnghia-j/ChordMini) is a newer research candidate with transformer models, supplied checkpoints and prediction smoothing. Its source license does not grant rights to third-party datasets. It is worth a later benchmark, rather than an automatic replacement based on paper results.

## Evaluation and app integration

Evaluate on representative songs with independent timed chord annotations, including silence and complex harmony. Compare root and major/minor accuracy first, then richer chord types, timing error, runtime and unknown coverage. No Moises parity claim is justified without direct evaluation.

Keep the result boundary as timed segments with start/end/chord labels so the UI's live transposition and playhead still work. Record recognizer name/version and vocabulary in the notice/metadata. The label helper now transposes both root and slash bass while preserving chord quality. Chordino output retains extended chords and inversions.

Report all download sizes from the pinned dependency and weight plan before installing. No remote GPU job was started. The subsequent benchmark downloaded the reported 12.53 MB source/checkpoint bundle; app integration required no further downloads.
