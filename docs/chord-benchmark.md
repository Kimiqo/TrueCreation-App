# Chord benchmark — 11 October 2026

User choice: **Chordino first**, BTC retained for benchmark comparisons. The app now invokes the local Chordino host when installed; otherwise it uses the explicitly labeled major/minor baseline. Installed-host failures surface as failed analysis jobs rather than silently changing recognizers.

## Controlled results

Time-sampled exact chord-label agreement, checked every 50 ms against generated ground truth. This is not an estimate of accuracy on real songs.

| Case | Current baseline | Chordino | BTC large vocabulary |
| --- | ---: | ---: | ---: |
| all-roots-triads | 90.0% | 98.0% | 95.92% |
| rhythmic-progression | 100.0% | 97.92% | 98.12% |
| extended-chords | 25.0% | 85.62% | 61.67% |
| silence | 100.0% | 100.0% | 100.0% |
| percussion-only | 100.0% | 100.0% | 100.0% |

Five deterministic fixtures total 124 seconds: all 12 major/minor roots with 2.5-second changes; a rhythmic C–G–Am–F sequence; major/minor sevenths, dominant seventh and sus4; silence; percussive noise. Harmonic synthesis uses five partials, controlled envelopes and seeded noise. No fixture is derived from or tailored to the uploaded song. Chordino's default dictionary includes richer labels; BTC uses its original 170-label checkpoint. Baseline has only major/minor triads.

The major/minor reduction score is a custom diagnostic, not mir_eval's official metric. Exact labels are normalized to sharps and colon qualities. Synthetic timbres favor some methods and omit many real musical situations; do not generalize these percentages to catalog-wide accuracy.

## Uploaded song: runtime and output behavior only

No ground-truth annotation is available. The actual uploaded 95-second mix remained local, was not downloaded from a third party or transmitted to a provider, and is excluded from Git.

| Method | Warm CPU analysis time | Number of segments |
| --- | ---: | ---: |
| baseline | 0.193 s | 62 |
| chordino | 0.765 s | 31 |
| btc-large | 0.282 s | 130 |

The runtimes are single runs with feature libraries warmed; include audio loading and preprocessing. BTC model initialization is excluded (about 0.06 s measured separately); Chordino starts a local executable for each file. Torch used four CPU threads. These measurements are neither latency guarantees nor separation timings. More/fewer segments do not prove accuracy. The Chordino output appears less fragmented and includes sevenths/inversions, but needs listening and independently annotated music evaluation.

## Validity checks and reproducibility

The Chordino host requests output descriptors after initialization, pads centered Hann-windowed frequency-domain input, and uses the official Vamp SDK FFT. An initial host lifecycle omission returned no labels; that run was discarded after diagnosis and the corrected comparison rerun. Empty output is an integration failure, not a zero-accuracy model result.

BTC preserves published CQT/chunking, normalization and 10/108-second label spacing. A removed NumPy `np.float` alias is patched in memory to `float`; downloaded source remains intact. Checkpoint loading uses `weights_only=True` with narrowly allowlisted NumPy scalar/dtype types. No arbitrary checkpoint execution or new Python dependencies.

From backend:

```sh
# Prints size, verifies pinned files, builds; --download permits missing downloads.
.venv/bin/python benchmarks/setup_chords.py --download
.venv/bin/python benchmarks/run_chords.py
```

Compiled executable, external source, checkpoint, generated WAV fixtures and per-song predictions remain in ignored `backend/data/chord-benchmark`. The manifest carries pinned source commits, exact sizes and SHA-256 digests. Benchmark host source is GPL-2.0-or-later, with the accompanying GPL text; this does not assign a license to the rest of the app. Source references: [Chordino](https://github.com/c4dm/nnls-chroma), [Vamp SDK](https://github.com/c4dm/vamp-plugin-sdk), [BTC](https://github.com/jayg996/BTC-ISMIR19).

Downloaded payload: **12,531,269 bytes** (11.95 MiB / 12.53 MB): 12,229,576 checkpoint bytes and 301,693 source bytes. No test songs, GPU SDKs or package-manager dependencies were installed. Compiled with the already-installed Boost headers and C++ toolchain.
