import random
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo


def parse_time_str(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Bad time format")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def parse_range(value: str) -> tuple[time, time]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError("Bad range format")
    return parse_time_str(parts[0]), parse_time_str(parts[1])


def today_str(tz: ZoneInfo) -> str:
    return datetime.now(tz).date().isoformat()


def sleep_window_for_date(base_date: datetime, start_time: time, end_time: time, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(base_date.date(), start_time, tzinfo=tz)
    end_dt = datetime.combine(base_date.date(), end_time, tzinfo=tz)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def pick_random_time(start_dt: datetime, end_dt: datetime) -> datetime:
    total_seconds = int((end_dt - start_dt).total_seconds())
    if total_seconds <= 0:
        return start_dt
    return start_dt + timedelta(seconds=random.randint(0, total_seconds))
