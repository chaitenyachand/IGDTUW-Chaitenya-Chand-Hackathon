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

    # --- API hardening (design section 12.1) ---
    api_token: str = ""                      # bearer token for write endpoints; empty = open (development only)
    rate_limit_per_minute: int = 600         # per client address, all endpoints
    write_rate_limit_per_minute: int = 60    # per client address, write endpoints

    # --- Pipeline behaviour ---
    audit_min_impact: float = 7.0            # signals at or above this impact are written to the audit ledger
    replay_pace_seconds: float = 1.0         # default pause between replay batches (0 = as fast as the models run)


settings = Settings()
