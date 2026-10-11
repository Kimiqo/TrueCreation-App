# TrueCreation App

A separate local development project for the sound-investigation MVP. No paid separation APIs. The marketing website lives in the sibling `TrueCreation-Website` directory.

## Current scope

- React/TypeScript browser workspace, project library and real audio upload.
- FastAPI backend and SQLite-backed durable project/job records for local development.
- Separate, single-process worker: FFmpeg decoding, basic analysis, self-hosted `htdemucs_6s` separation, aligned WAVs and ZIP export.
- Listen / Analyse tabs, shared Web Audio playback clock, per-stem mute/solo/volume, actual stem waveforms, and passage selection.
- Live −/+ tempo (50–150%, 5% steps) and transpose (−12 to +12 semitones) controls using SoundTouch AudioWorklet. Shared controls work in both Listen and Analyse; downloadable transforms are queued separately using librosa.
- Supplied TrueCreation logo in the workspace sidebar.
- Timed, estimated major/minor chord progression from the original mix, with uncertainty/silence labelled N. This baseline does not recognize extensions or inversions.
- Saved passage measurements with explicit `catalog_unavailable` results; no fabricated source matches.
- Optional MDX23C drum separation on clicking Separate drums: kick, snare, hi-hat, toms, ride, crash in a collapsible group. Expand drums starts separation if needed and switches to components when ready; Collapse drums restores the combined parent. Never play both. This is local evaluation with unresolved weight licensing.

This is a **local single-user build**. Bind both services to `127.0.0.1`. Authentication, tenant isolation, hosted storage, usage/billing controls, deletion, production worker leases and catalog matching are not implemented yet. SQLite is the local implementation of the future PostgreSQL job boundary. Do not expose this server publicly.

## Start development

Prerequisites: Python 3.10+, Node.js compatible with Vite, and FFmpeg/ffprobe on PATH. Model compatibility and CPU speed depend on the selected Python/PyTorch versions.

From `TrueCreation-App/backend`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-separation.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, from the same backend directory:

```sh
.venv/bin/python -m app.worker
```

In a third terminal, from `TrueCreation-App/frontend`:

```sh
npm install
npm run dev
```

Open http://127.0.0.1:5174. API documentation: http://127.0.0.1:8000/docs.

The first separation downloads pretrained model weights. Local CPU processing can be slow. Uploads are capped at 3 minutes and 75 MB to bound development memory and processing. Every output is generated from the actual upload; nothing is simulated. `other` includes remaining sounds, and piano/guitar quality is experimental.

Audio files, logs, manifests, ZIPs and the SQLite database are stored under `backend/data` (ignored). Set `TRUECREATION_DATA` to move the local workspace. Run exactly one audio worker; a file lock prevents concurrent workers.

## Validation

```sh
# backend
.venv/bin/python -m unittest discover -s tests -v
# frontend
npm run build
```

API tests exercise real upload/decoding, job claims, invalid audio, passage bounds, persistence and export. They substitute expensive separation with explicitly controlled fixtures; passing them does not prove model quality. Real Demucs inference must be checked separately.

Initial validation: all six initial API tests and the frontend production build passed. `backend/smoke_separation.py` also ran the actual model on a two-second synthetic signal and verified six stereo outputs with identical frame counts. This checks the inference pipeline, not music separation quality. `backend/requirements-local.lock.txt` records the installed development environment (Python 3.13 on macOS); use the requirements files above for other platforms.

The first uploaded 95-second MP3 completed the full local worker pipeline. Browser verification confirmed playback progress and a saved eight-second drum investigation, with no reported browser errors. Its exported ZIP contains all six WAV stems and `analysis.json`. Separation quality still needs listening evaluation across varied music. A browser snapshot is saved in `docs/workspace-preview.png`.

## MDX23C setup and download sizes

The pinned v0.1.0 inference source is included under `backend/vendor/mdxnet-infer`, with its MIT license and provenance. It was downloaded as a 129,898-byte source archive (~127 KiB); no additional Python or npm dependency installation was needed. The six-component checkpoint is **437,652,699 bytes (417.38 MiB / 437.65 MB)**; configuration is **2,417 bytes**. Both were SHA-256 verified before caching under `backend/data/model-cache/mdx23c`.

On a new machine, download the checkpoint and YAML listed in `backend/vendor/mdxnet-infer/PROVENANCE.json` from the upstream `weights-drumsep-v1` release into that cache directory using their original names. The worker verifies both digests and refuses implicit downloads. Never commit the checkpoint to Git. Original model-weight licensing is unresolved; the MIT code license is not a commercial license for the checkpoint. Public/commercial deployment remains unapproved from a licensing standpoint.

The adapter runs pinned MDX23C in a subprocess on CPU and uses restricted PyTorch `weights_only=True` loading. Its six child files must match the parent timeline, sample rate and stereo shape before publication. A subprocess releases model memory after inference. Six children replace one full drum track during expanded listening, giving eleven active tracks. Original export retains the full parent for comparison as well as the children.

## Feature jobs

Selecting a completed project queues a deduplicated analysis job for its waveforms/chord estimates, including existing projects. Drum expansion is requested explicitly. Tempo/transpose export copies are requested with Prepare download. These jobs are stored separately from the original project result: failure or retry leaves the initial six stems available. Interrupted jobs requeue on worker restart. Work runs sequentially on the local worker.

Live preview runs in the browser without rendering new files or reloading stems. All sources use a shared start time and playback rate; a single AudioWorklet processes the mixed signal with rate-compensated pitch shifting. Changing speed integrates the elapsed original-song position first. Pausing/seeking creates a fresh processor on resume to avoid stale buffered audio. The worklet adds a small DSP delay; large shifts may introduce audible artifacts. Live preview and librosa exports use different algorithms and may sound slightly different.

Original uploads and stems remain immutable; original stem downloads and transformed exports are separate. Chord labels update immediately with transposition, and the current chord follows original-song seconds. Download completion never swaps the live player onto rendered files. Prepared downloads show their own settings, even if live controls have changed since requesting them.

New browser DSP dependency: `@soundtouchjs/audio-worklet` 2.1.1 and three matching dependencies, MPL-2.0. Combined compressed registry payloads: **151,622 bytes (~148 KiB)**; unpacked package metadata total: 645,513 bytes (~630 KiB). The emitted worklet asset is 72.92 kB. npm also installed Vite’s optional macOS `fsevents` 2.3.3 watcher (22,808-byte compressed package). Combined payload size for these five packages is 174,430 bytes (~170 KiB); npm metadata/audit traffic is additional. No additional model downloads are required for live controls.

For actual browser DSP verification open `http://127.0.0.1:5174/tests/live-audio.html` while Vite runs. It checks a scheduled live pitch/tempo change (220→440 Hz while speed changes to 125%), transformed duration, and playhead continuity across tempo changes. Production build and these five checks passed; six- and eleven-stem playback and transposed chord seeking were exercised in the app. Chord accuracy remains unverified on real songs; the selected Chordino upgrade is described below.

Waveform seeking becomes available after pressing play to load audio. Expand drums / Collapse drums changes the active audio set and releases previous browser buffers. Combined drums remain active until the requested components are ready; cached components are reused on future expansions. The chord progression in Analyse is collapsed by default; its disclosure controls visibility while current-chord tracking continues. Browser audio memory can still be substantial for long tracks at eleven stems. There is no cross-song reference catalog, lead/backing vocal separator, or MIDI transcription in this build.

No provider credentials or cloud purchases are required for this local development build. The initial hosted MVP spending ceiling remains $50 total.

## Chordino recognition

Chordino is the selected recognizer; BTC remains a benchmark comparison, not a runtime dependency. Run `backend/benchmarks/setup_chords.py` with the backend Python from the backend directory to verify cached sources and build the standalone GPL CLI. For a new machine, `--download` fetches the pinned 12.53 MB benchmark bundle (including the BTC comparison checkpoint); the script prints the size first. Building needs a C++ compiler and Boost headers. No automatic runtime downloads occur. Set `TRUECREATION_CHORDINO` to an alternative host executable path, or use the default under the data directory. The built executable is local and excluded from Git.

API health exposes the selected method. Existing completed projects upgrade their analysis once when the recognizer changes; missing Chordino uses the labeled major/minor fallback. An installed host failure is visible and retryable. Revised chord results invalidate the export cache. Chordino supports a richer dictionary, but predictions remain estimates. See [controlled benchmark and limitations](docs/chord-benchmark.md).

Analyse shows a collapsible sequence with playing-now/up-next chords, timed seek cards, active progress and extended/inversion labels. Transposition shifts both the root and slash bass. No real-song accuracy or Moises parity has been established.
