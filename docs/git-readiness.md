# Git push assessment — 11 October 2026

Repository: `TrueCreation-App`, branch `main`, origin `https://github.com/Kimiqo/TrueCreation-App.git`. The sibling marketing website is outside this repository. At assessment time there were no commits, tracked files, or staged changes; all push candidates are untracked. Nothing was staged, committed or pushed by this assessment.

## Suitable to commit

- Backend/frontend application source, unit/browser verification files and configuration.
- Python requirements and npm package/lock files. `requirements-local.lock.txt` describes this Mac environment; portable installs should use the general requirements files.
- User-provided logo (`frontend/public/logo.png`, largest app asset).
- README, architecture/model/GPU/chord assessment documentation and anonymous benchmark metrics.
- Benchmark scripts, pinned download manifest and GPL notice for the standalone Chordino CLI host.
- Vendored MDX inference source with its MIT LICENSE and PROVENANCE. This contains no checkpoint.

The application has no top-level license selected yet. Do not assume third-party licenses apply to app-owned code. If the repository is public, choose an app license according to intended distribution; a private repository can preserve that decision for later.

## Excluded from commits

| Files | Reason |
| --- | --- |
| `backend/data/` | Uploaded music, generated stems/exports, per-song analysis, database, model cache, and benchmark binaries/weights/fixtures |
| `.venv/`, `node_modules/`, `dist/`, caches/build metadata | Reproducible dependencies and generated output |
| `.env`, `.env.*` except `.env.example`, logs, databases | Local configuration/state; credentials may appear here |
| `.vibe-wise/` | Personal learning notes |
| `docs/*preview*.png` | Demo screenshots reveal the uploaded track title |
| Audio formats and checkpoint formats anywhere | Prevent accidental additions outside the normal data directory |
| `.DS_Store` | Machine-generated metadata |

Hardened `.gitignore` accordingly. Ignore rules do not remove files that are already tracked, but there were no tracked files here. Verified that both Demucs/MDX caches, BTC checkpoint, learning profile, app screenshot, node_modules and dist are excluded.

## Scan and limits

Scanned Git-visible source candidates for private-key headers, GitHub tokens, AWS access-key IDs, and common literal credential assignments without printing matched values. No matches found. Final scan: 57 source candidates totaling 1,923,966 bytes (about 1.9 MB), including the integrated recognizer and tests. No candidate exceeded 10 MiB. This is a heuristic source scan, not a guarantee that every secret format is detectable. Generated audio/model files were excluded, rather than inspected or included in the source scan.

A push of the source is distinct from publishing a working backend. The current app is a localhost, single-user MVP; deployment still needs authentication, isolated storage/job access and licensing resolution for model weights. Model-weight rights are separate from the MIT inference code license.

## Before first push

Review `git status --short --untracked-files=all` and the candidate diff after staging selected source paths. Create the initial commit, then push `main` to origin. No push is possible before an initial commit exists. No GitHub repository visibility was queried or changed, and no credentials were requested.
