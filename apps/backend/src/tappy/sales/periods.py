from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def local_day(moment: datetime, zone: ZoneInfo) -> date:
    return moment.astimezone(zone).date()


def day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, zone)
    end = datetime.combine(day + timedelta(days=1), time.min, zone)
    return start, end


@dataclass(frozen=True)
class BusinessDay:
    day: date
    zone: ZoneInfo
