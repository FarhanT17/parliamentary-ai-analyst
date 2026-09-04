"""
Application configuration for Parliamentary AI Analyst.

Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )

    LLM_MODEL = os.getenv(
        "LLM_MODEL",
        "gpt-4o-mini",
    )

    VECTOR_DIMENSION = 384

    CHUNK_SIZE = 700
    CHUNK_OVERLAP = 120

    MAX_QUERY_LENGTH = 500
    DEFAULT_TOP_K = 5

    DATA_DIR = os.getenv("DATA_DIR", "backend/data")

    COLLECT_FRESH_DATA = os.getenv(
        "COLLECT_FRESH_DATA",
        "true",
    ).lower() == "true"

    @classmethod
    def validate(cls):
        """Validate application configuration."""

        errors = []

        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is not configured.")

        if cls.CHUNK_OVERLAP >= cls.CHUNK_SIZE:
            errors.append(
                "CHUNK_OVERLAP must be smaller than CHUNK_SIZE."
            )

        if errors:
            raise ValueError("Configuration errors: " + "; ".join(errors))

        return True