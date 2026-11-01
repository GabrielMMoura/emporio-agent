"""Current time in the store's time zone. Tests replace `now` to freeze the date."""

from datetime import datetime
from zoneinfo import ZoneInfo

from emporio_agent.config import STORE_TIMEZONE

STORE_TZ = ZoneInfo(STORE_TIMEZONE)


def now() -> datetime:
    return datetime.now(STORE_TZ)
