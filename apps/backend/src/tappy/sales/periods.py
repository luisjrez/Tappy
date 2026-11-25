from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class BusinessDay:
    day: date
    zone: ZoneInfo

    @classmethod
    def today(cls, now: datetime, zone: ZoneInfo) -> BusinessDay:
        return cls(now.astimezone(zone).date(), zone)

    @property
    def bounds(self) -> tuple[datetime, datetime]:
        start = datetime.combine(self.day, time.min, self.zone)
        end = datetime.combine(self.day + timedelta(days=1), time.min, self.zone)
        return start, end
