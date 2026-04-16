"""CLI entry so the pipeline can be exercised without the API/UI.

Usage:
    python -m app.pipeline.cli <url> [--output-dir PATH] [--device cpu|mps]
"""
from __future__ import annotations
import argparse
import json
import uuid
from pathlib import Path
from app.pipeline.orchestrator import Orchestrator
from app.pipeline.download import DownloadStage
from app.pipeline.audio import AudioStage
from app.pipeline.speech import SpeechStage
from app.pipeline.sfx import SfxStage
from app.pipeline.music import MusicStage
from app.pipeline.finalize import FinalizeStage
from app.storage.asset_storage import LocalAssetStorage


def build_default_stages() -> list:
    return [
        DownloadStage(),
        AudioStage(),
        SpeechStage(),
        SfxStage(),
        MusicStage(),
        FinalizeStage(),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--output-dir", default="./outputs")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--model", default="htdemucs_ft")
    args = ap.parse_args()

    storage = LocalAssetStorage(Path(args.output_dir))
    job_id = uuid.uuid4().hex[:12]
    job_dir = storage.create_job_dir(job_id=job_id, slug="cli")

    def emit(event):
        print(json.dumps(event))

    orch = Orchestrator(stages=build_default_stages(), emit=emit)
    result = orch.run(
        job_id=job_id,
        job_dir=job_dir,
        params={
            "url": args.url,
            "device": args.device,
            "model": args.model,
            "min_cluster_size": 2,
            "clip_min_ms": 300,
            "clip_max_ms": 1500,
            "source_url": args.url,
        },
    )
    print(json.dumps({"final": result}))


if __name__ == "__main__":
    main()
