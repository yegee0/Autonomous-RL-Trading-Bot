import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: List[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        ).split(",")
    )
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    hf_model_repo: str = os.getenv("HF_MODEL_REPO", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
