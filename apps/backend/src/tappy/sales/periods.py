import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


class PeriodKind(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def last_day_of_month(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


@dataclass(frozen=True)
class BusinessPeriod:
    kind: PeriodKind
    first: date
    last: date
    zone: ZoneInfo

    @classmethod
    def containing(cls, kind: PeriodKind, day: date, zone: ZoneInfo) -> BusinessPeriod:
        match kind:
            case PeriodKind.DAY:
                return cls(kind, day, day, zone)
            case PeriodKind.WEEK:
                monday = day - timedelta(days=day.weekday())
                return cls(kind, monday, monday + timedelta(days=6), zone)
            case PeriodKind.MONTH:
                return cls(kind, day.replace(day=1), last_day_of_month(day), zone)

    @classmethod
    def at(
        cls, kind: PeriodKind, day: date | None, now: datetime, zone: ZoneInfo
    ) -> BusinessPeriod:
        return cls.containing(kind, day or now.astimezone(zone).date(), zone)

    @property
    def bounds(self) -> tuple[datetime, datetime]:
        start = datetime.combine(self.first, time.min, self.zone)
        end = datetime.combine(self.last + timedelta(days=1), time.min, self.zone)
        return start, end

    @property
    def days(self) -> list[date]:
        count = (self.last - self.first).days + 1
        return [self.first + timedelta(days=offset) for offset in range(count)]

    def local_date(self, moment: datetime) -> date:
        return moment.astimezone(self.zone).date()
