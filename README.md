# ExtractAssets

Local tool that splits Instagram Reels / YouTube Shorts audio into **speech**, deduplicated **sound effects**, and **music** — with a web UI.

## Requirements
- macOS (Apple Silicon recommended for MPS-accelerated Demucs)
- Python 3.11+, [uv](https://github.com/astral-sh/uv)
- Node 20+, [pnpm](https://pnpm.io)
- `ffmpeg` on your PATH (`brew install ffmpeg`)

## Install
```bash
./scripts/setup.sh
```

## Run
```bash
./scripts/run.sh
```
Opens `http://localhost:8000` in your browser.

## Dev
```bash
./scripts/dev.sh
```
Frontend on `:5173` with HMR, backend on `:8000` with reload.

## Design
- Spec: [`docs/superpowers/specs/2026-04-16-extractassets-design.md`](docs/superpowers/specs/2026-04-16-extractassets-design.md)
- Plan: [`docs/superpowers/plans/2026-04-16-extractassets.md`](docs/superpowers/plans/2026-04-16-extractassets.md)
