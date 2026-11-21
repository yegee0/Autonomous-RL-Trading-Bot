"""Download the pre-trained generalist PPO model from Hugging Face Hub.

Usage:
    HF_MODEL_REPO=user/trademaster-rl-generalist python scripts/download_model.py
    # or
    python scripts/download_model.py --repo user/trademaster-rl-generalist

Downloads:
    model_general.zip
    model_general_vecnorm.pkl
into ``models/trained/``.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "trained")

FILES = ("model_general.zip", "model_general_vecnorm.pkl")


def download(repo: str, revision: str = "main") -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface_hub is not installed. Run: pip install huggingface_hub", file=sys.stderr)
        sys.exit(1)

    os.makedirs(MODELS_DIR, exist_ok=True)
    for fname in FILES:
        print(f"[download] {repo}:{revision}/{fname}")
        path = hf_hub_download(
            repo_id=repo,
            filename=fname,
            revision=revision,
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False,
        )
        print(f"[download]   -> {path}")

    print("[download] done. Restart the backend to pick up the new model.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=os.getenv("HF_MODEL_REPO", ""),
                   help="Hugging Face repo id, e.g. user/trademaster-rl-generalist")
    p.add_argument("--revision", default=os.getenv("HF_MODEL_REV", "main"))
    args = p.parse_args()

    if not args.repo:
        print("No repo specified. Pass --repo or set HF_MODEL_REPO.", file=sys.stderr)
        sys.exit(2)
    download(args.repo, args.revision)


if __name__ == "__main__":
    main()
