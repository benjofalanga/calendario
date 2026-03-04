from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from django.contrib.auth.models import User

from .models import DayOffRequest, UserCarryoverOverride

RESERVED_STATUSES = (
    DayOffRequest.STATUS_APPROVED,
)


@dataclass
class YearQuotaLedger:
    year: int
    allowance: int
    carryover_start: int
    q1_used: int
    current_used: int
    as_of: date

    @property
    def carryover_used(self) -> int:
        return min(self.carryover_start, self.q1_used)

    @property
    def carryover_left(self) -> int:
        return max(self.carryover_start - self.carryover_used, 0)

    @property
    def current_left(self) -> int:
        return max(self.allowance - self.current_used, 0)

    @property
    def carryover_deadline(self) -> date:
        return date(self.year, 3, 31)

    @property
    def carryover_expired(self) -> bool:
        return self.as_of > self.carryover_deadline

    @property
    def carryover_available_now(self) -> int:
        if self.carryover_expired:
            return 0
        return self.carryover_left

    @property
    def total_left(self) -> int:
        return self.carryover_available_now + self.current_left

    def try_allocate(self, request_date: date):
        if request_date.year != self.year:
            raise ValueError("Date year does not match quota ledger year.")

        q1_deadline = date(self.year, 3, 31)
        is_q1_date = request_date <= q1_deadline

        # In Q1, consume previous-year carryover first.
        if is_q1_date and self.q1_used < self.carryover_start:
            self.q1_used += 1
            return True, "carryover"

        # Then consume current-year allowance.
        if self.current_used < self.allowance:
            self.current_used += 1
            if is_q1_date:
                self.q1_used += 1
            return True, "current"

        return False, None


def build_quota_ledger(
    user: User,
    allowance: int,
    year: int,
    statuses: Iterable[str] = RESERVED_STATUSES,
    exclude_request_id: Optional[int] = None,
    as_of: Optional[date] = None,
) -> YearQuotaLedger:
    status_values = list(statuses)
    q1_deadline = date(year, 3, 31)

    query = DayOffRequest.objects.filter(user=user, status__in=status_values)
    if exclude_request_id is not None:
        query = query.exclude(id=exclude_request_id)

    prev_year_used = query.filter(date__year=year - 1).count()
    current_year_used = query.filter(date__year=year).count()
    q1_used = query.filter(date__year=year, date__lte=q1_deadline).count()

    override = UserCarryoverOverride.objects.filter(user=user, year=year).first()
    if override:
        carryover_start = override.days
    else:
        had_previous_year_entitlement = user.date_joined.date() <= date(year - 1, 12, 31)
        if had_previous_year_entitlement:
            carryover_start = max(allowance - prev_year_used, 0)
        else:
            carryover_start = 0
    carryover_consumed = min(carryover_start, q1_used)
    current_used = max(current_year_used - carryover_consumed, 0)

    return YearQuotaLedger(
        year=year,
        allowance=allowance,
        carryover_start=carryover_start,
        q1_used=q1_used,
        current_used=current_used,
        as_of=as_of or date.today(),
    )
