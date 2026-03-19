"""Interview module configuration."""

import os


class Settings:
    """Application settings loaded from environment variables."""

    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://localhost/superinsight"
    )


settings = Settings()
