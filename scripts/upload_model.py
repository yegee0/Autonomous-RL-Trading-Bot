"""Upload the generalist PPO model to the Hugging Face Hub.

Usage:
    HF_TOKEN=hf_xxx HF_MODEL_REPO=user/trademaster-rl-generalist \
        python scripts/upload_model.py
    # or:
    python scripts/upload_model.py --repo user/trademaster-rl-generalist --token $HF_TOKEN

Pushes:
    models/trained/model_general.zip
    models/trained/model_general_vecnorm.pkl
    README.md (auto-generated model card)
Creates the repo if it doesn't exist.
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "trained")

ARTIFACTS = ("model_general.zip", "model_general_vecnorm.pkl")


MODEL_CARD = textwrap.dedent(
    """\
    ---
    license: mit
    library_name: stable-baselines3
    tags:
      - reinforcement-learning
      - trading
      - ppo
      - finance
    ---

    # TradeMaster RL Generalist

    A single PPO policy trained with scale-invariant observations so it generalises
    across crypto and equities. Produces discrete action signals (hold / buy 25-50-100%
    / sell 25-50-100%) that the TradeMaster backend turns into trade suggestions.

    ## Files
    - `model_general.zip` — PPO weights (Stable Baselines3 format)
    - `model_general_vecnorm.pkl` — paired `VecNormalize` statistics (needed for inference)

    ## Observation space (8-dim, unit-less)
    `[cash_ratio, position_ratio, ret_1, ret_5, rsi/100, (macd-signal)/price, atr/price, sentiment]`

    ## Usage
    See <https://github.com/your-user/trademaster> — `scripts/download_model.py` pulls both
    files into `models/trained/` and the backend loads them automatically on startup.
    """
)


def ensure_repo(api, repo_id: str) -> None:
    try:
        api.repo_info(repo_id=repo_id, repo_type="model")
        print(f"[upload] repo exists: {repo_id}")
    except Exception:
        print(f"[upload] creating repo: {repo_id}")
        api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)


def upload(repo: str, token: str, commit_msg: str) -> None:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub is not installed. Run: pip install huggingface_hub", file=sys.stderr)
        sys.exit(1)

    missing = [f for f in ARTIFACTS if not os.path.isfile(os.path.join(MODELS_DIR, f))]
    if missing:
        print(f"Missing artefacts: {missing}. Train first with scripts/train_general.py.", file=sys.stderr)
        sys.exit(2)

    api = HfApi(token=token)
    ensure_repo(api, repo)

    # Model card
    card_path = os.path.join(MODELS_DIR, "_README_upload.md")
    with open(card_path, "w", encoding="utf-8") as f:
        f.write(MODEL_CARD)
    try:
        api.upload_file(
            path_or_fileobj=card_path,
            path_in_repo="README.md",
            repo_id=repo,
            repo_type="model",
            commit_message=commit_msg,
        )
        print("[upload] README.md -> pushed")

        for fname in ARTIFACTS:
            local = os.path.join(MODELS_DIR, fname)
            api.upload_file(
                path_or_fileobj=local,
                path_in_repo=fname,
                repo_id=repo,
                repo_type="model",
                commit_message=commit_msg,
            )
            print(f"[upload] {fname} -> pushed")
    finally:
        try:
            os.remove(card_path)
        except OSError:
            pass

    print(f"\nDone. View at https://huggingface.co/{repo}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=os.getenv("HF_MODEL_REPO", ""))
    p.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    p.add_argument("--message", default="Update TradeMaster RL generalist checkpoint")
    args = p.parse_args()

    if not args.repo:
        print("Pass --repo or set HF_MODEL_REPO.", file=sys.stderr)
        sys.exit(2)
    if not args.token:
        print("Pass --token or set HF_TOKEN (needs write scope).", file=sys.stderr)
        sys.exit(2)

    upload(args.repo, args.token, args.message)


if __name__ == "__main__":
    main()
