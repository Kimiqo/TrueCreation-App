# MDX23C drum expansion assessment

Status: implemented locally after user authorization. Source is pinned to v0.1.0, commit 84458e9ef6306a895c4917f03c4f65ac3a22f596. Listen / Analyse tabs are implemented. This document retains design context; current behavior is documented in README.md.

## What we would use

MDX23C names an architecture, not a guarantee about every model trained with it. The candidate is the aufr33/jarredou six-component DrumSep checkpoint, through the [OpenMIRLab inference package](https://github.com/openmirlab/mdxnet-infer). Its documented outputs are kick, snare, toms, hi-hat, ride, and crash. Our pinned adapter uses CPU inference and verifies downloaded weights against SHA-256 checksums. The original weight host is unavailable; the package provides a mirror.

## Proposed integration

Upload → existing Demucs six-stem job → ready to listen → requested drum expansion → isolated drum inference job → validate six children → publish drum manifest and per-child waveforms.

This is a proposal, not an agreed design. Keep the existing result usable while expansion runs or fails. Give expansion its own queued/processing/completed/failed state, retry behavior, error, and attempt count. Use the existing local worker sequentially to bound peak model memory; release the base model before loading the drum model. Cache immutable results by parent drum audio hash, model/checkpoint digest, and settings.

Implement the existing `DrumSeparator` contract in `backend/app/separation.py`. The current empty adapter alone does not wire expansion into the system: the API, store, worker, manifests, exports, mixer, and playback engine also need changes. Make stem rendering data-driven rather than relying on six hardcoded names.

Retain the full drums file for comparison. During expanded playback use the six drum children instead of the full drum parent, to avoid doubling drums. Five existing non-drum tracks plus six children gives eleven active tracks. Combining ride and crash gives ten; that grouping is a product choice, not a different pretrained five-output checkpoint. Any residual derived from parent minus summed children is a reconstruction difference, not a newly recognized instrument.

## Compatibility, cost, and quality

The [package requirements](https://github.com/openmirlab/mdxnet-infer/blob/master/pyproject.toml) overlap our existing PyTorch, NumPy, SoundFile, librosa, YAML, and requests stack. Python 3.13 is our current local environment; upstream advertises 3.10–3.12, so compatibility still needs a real smoke test. Pin the tested package commit and weight digests instead of a moving branch. Prefer an isolated evaluation environment before touching working dependencies. The implemented source uses existing dependencies; no package upgrades were needed.

No paid inference API is needed. Local inference uses the current machine, but runtime, RAM, and hosted cost have not been measured. Benchmark a 10–15 second drum excerpt first, then the full existing track. Record cold/warm runtime and peak memory. At three minutes, eleven fully decoded stereo 44.1 kHz float32 tracks consume roughly 699 MB before other browser overhead; loading every output eagerly would be wasteful. Child audio should be loaded when expansion is selected, with unused buffers released.

Two-stage separation compounds errors: MDX23C receives Demucs drum leakage and missing transients. Listen for kick/snare bleed, lost hits, smeared cymbals, and artifacts. Require finite samples, stereo 44.1 kHz, consistent frame count, and aligned transients before publishing. Use a controlled mixture with known drum components for quantitative evaluation as well as varied real music; neither a synthetic tone nor one song establishes quality.

## Licensing limit

The [checkpoint registry](https://github.com/openmirlab/mdxnet-infer/blob/master/src/mdxnet_infer/config/checkpoints.toml) explicitly records unknown original weight licensing. MIT inference code does not establish commercial rights to these weights. We cannot currently describe this model as cleared for a public/commercial release, or infer that an investor demo is automatically permitted. Keep evaluation and release decisions distinct; seek documented author permission or a checkpoint with explicit suitable terms before deployment.

## Resolved learner decisions

The user selected expansion only after Separate drums is clicked, inside a collapsible group, and explicitly requested implementation. The UI provides Use drum components / Use full drums to switch mutually exclusive playback sets. Collapsing the group only changes visibility.
