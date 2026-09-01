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

    # New Relic logging
    newrelic_license_key: str = "350ed5b6c2fb675958bb75486c57c570679dNRAL"

    # PagerDuty
    pagerduty_api_token: str = "u+2Kf6xufQUhr1CLJsBw"
    pagerduty_service_id: str = "PUMAG77"
    pagerduty_priority_id: str = "P9VA1XZ"
    pagerduty_escalation_id: str = "P0Z7O6F"
    pagerduty_from_email: str = "gaurav.chandak@tcs.com"

    # Anomaly detection thresholds
    failure_rate_threshold: float = 0.3

    model_config = {"env_file": ".env", "extra": "ignore"}
