"""Environment configuration for QueueStorm Investigator."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None
    model_name: str
    port: int
    request_timeout_seconds: int
    health_timeout_seconds: int

    @staticmethod
    def load() -> "Settings":
        port_raw = os.getenv("PORT", "8000")
        try:
            port = int(port_raw)
        except ValueError:
            port = 8000
        return Settings(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name=os.getenv("MODEL_NAME", "llama-3.3-70b-versatile"),
            port=port,
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            health_timeout_seconds=int(os.getenv("HEALTH_TIMEOUT_SECONDS", "60")),
        )


settings = Settings.load()