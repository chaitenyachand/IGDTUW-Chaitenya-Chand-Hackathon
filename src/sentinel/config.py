from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://sentinel:sentinel@localhost:5432/sentinel"
    redis_url: str = "redis://localhost:6379/0"

    sec_user_agent: str = "SENTINEL Hackathon contact@example.com"
    fred_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "sentinel-hackathon/0.1"

    gdelt_poll_seconds: int = 900
    rss_poll_seconds: int = 300
    edgar_poll_seconds: int = 600
    reddit_poll_seconds: int = 120

    bluesky_jetstream_url: str = "wss://jetstream2.us-east.bsky.network/subscribe"
    cors_origins: str = "*"
    log_level: str = "INFO"


settings = Settings()
