"""CMS Unified settings — Supabase + Resend, no AWS."""

from pydantic_settings import BaseSettings


class UnifiedSettings(BaseSettings):
    service_name: str = "cms-unified"
    base_url: str = "https://cms-unified-api.vercel.app"

    # Supabase (required)
    supabase_url: str = ""
    supabase_key: str = ""  # use service_role key for backend

    # Resend email (optional — notifications are skipped if not set)
    resend_api_key: str = ""
    from_email: str = "onboarding@resend.dev"

    # Cron job security
    cron_secret: str = ""

    # Chaos engineering
    chaos_mode: bool = False

    # Anomaly detection thresholds
    failure_rate_threshold: float = 0.3

    model_config = {"env_file": ".env", "extra": "ignore"}
