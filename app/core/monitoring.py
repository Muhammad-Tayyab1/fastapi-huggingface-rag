import sentry_sdk

from app.core.config import settings


def init_monitoring() -> None:
    dsn = settings.sentry_dsn.get_secret_value()
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
