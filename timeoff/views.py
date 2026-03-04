import calendar
import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .forms import (
    CountryForm,
    DaySelectionForm,
    EmployeeDirectUpdateForm,
    EmployeeProfileUpdateForm,
    ManagerUserCreateForm,
    PublicHolidayForm,
)
from .models import Country, DayOffRequest, EmployeeProfile, PublicHoliday
from .quota import RESERVED_STATUSES, build_quota_ledger
from .utils import is_manager

manager_required = user_passes_test(is_manager, login_url="login")


class AppLoginView(LoginView):
    template_name = "registration/login.html"

    def form_invalid(self, form):
        messages.error(self.request, "Wrong username or password. Please try again.")
        return super().form_invalid(form)


@login_required
def home(request: HttpRequest) -> HttpResponse:
    if is_manager(request.user):
        return redirect("manager_dashboard")
    return redirect("employee_calendar")


def _safe_int(raw_value: str, fallback: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return fallback
    return min(max(value, minimum), maximum)


def _parse_date_filters(request: HttpRequest):
    from_raw = request.GET.get("date_from", "")
    to_raw = request.GET.get("date_to", "")

    parsed_from = None
    parsed_to = None

    try:
        if from_raw:
            parsed_from = date.fromisoformat(from_raw)
    except ValueError:
        parsed_from = None

    try:
        if to_raw:
            parsed_to = date.fromisoformat(to_raw)
    except ValueError:
        parsed_to = None

    return from_raw, to_raw, parsed_from, parsed_to


def _parse_selected_dates(raw: str):
    if not raw:
        return []

    raw = raw.strip()
    if not raw:
        return []

    values = []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = []
        values = parsed if isinstance(parsed, list) else []
    else:
        values = [item.strip() for item in raw.split(",")]

    parsed_dates = []
    for raw_date in values:
        try:
            parsed_dates.append(date.fromisoformat(raw_date))
        except (TypeError, ValueError):
            continue

    return sorted(set(parsed_dates))


def _monthly_range(year: int, month: int):
    start_day = date(year, month, 1)
    end_day = date(year, month, calendar.monthrange(year, month)[1])
    return start_day, end_day


def _safe_next_url(request: HttpRequest, fallback_name: str):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse(fallback_name)


def _parse_json_list(raw_value: str):
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return []


class EmployeeCalendarView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        profile, _ = EmployeeProfile.objects.get_or_create(user=request.user)

        today = date.today()
        month = _safe_int(request.GET.get("month", ""), today.month, 1, 12)
        year = _safe_int(request.GET.get("year", ""), today.year, today.year - 5, today.year + 5)
        selected_dates_seed = _parse_selected_dates(request.GET.get("selected_dates", ""))

        request_rows = list(
            DayOffRequest.objects.filter(user=request.user).exclude(status=DayOffRequest.STATUS_CANCELLED)
            .select_related("country")
            .values("id", "date", "status", "note", "revoke_requested")
        )

        holiday_rows = []
        if profile.country_id:
            holiday_rows = list(
                PublicHoliday.objects.filter(country=profile.country).values("date", "name")
            )
        month_holiday_count = 0
        for row in holiday_rows:
            if row["date"].year == year and row["date"].month == month:
                month_holiday_count += 1

        allowance = profile.annual_day_off_allowance
        quota_ledger = build_quota_ledger(
            user=request.user,
            allowance=allowance,
            year=year,
            statuses=RESERVED_STATUSES,
        )

        approved_this_year = DayOffRequest.objects.filter(
            user=request.user,
            date__year=year,
            status=DayOffRequest.STATUS_APPROVED,
        ).count()
        pending_this_year = DayOffRequest.objects.filter(
            user=request.user,
            date__year=year,
            status=DayOffRequest.STATUS_PENDING,
        ).count()
        pending_requests = DayOffRequest.objects.filter(
            user=request.user,
            status=DayOffRequest.STATUS_PENDING,
        ).order_by("date")

        context = {
            "month": month,
            "year": year,
            "month_options": list(enumerate(calendar.month_name))[1:],
            "selected_dates_seed_json": json.dumps([item.isoformat() for item in selected_dates_seed]),
            "day_form": DaySelectionForm(),
            "country": profile.country,
            "allowance": allowance,
            "approved_this_year": approved_this_year,
            "pending_this_year": pending_this_year,
            "pending_requests": pending_requests,
            "previous_year": year - 1,
            "carryover_deadline": date(year, 3, 31),
            "month_holiday_count": month_holiday_count,
            "carryover_left": quota_ledger.carryover_left,
            "carryover_available_now": quota_ledger.carryover_available_now,
            "carryover_expired": quota_ledger.carryover_expired,
            "current_year_left": quota_ledger.current_left,
            "total_remaining": quota_ledger.total_left,
            "request_data_json": json.dumps(
                [
                    {
                        "id": row["id"],
                        "date": row["date"].isoformat(),
                        "status": row["status"],
                        "note": row["note"],
                        "revoke_requested": row["revoke_requested"],
                    }
                    for row in request_rows
                ]
            ),
            "holiday_data_json": json.dumps(
                [
                    {
                        "date": row["date"].isoformat(),
                        "name": row["name"],
                    }
                    for row in holiday_rows
                ]
            ),
        }

        return render(request, "timeoff/employee_calendar.html", context)

    def post(self, request: HttpRequest) -> HttpResponse:
        profile, _ = EmployeeProfile.objects.get_or_create(user=request.user)
        form = DaySelectionForm(request.POST)
        month = _safe_int(request.POST.get("month", ""), date.today().month, 1, 12)
        year = _safe_int(request.POST.get("year", ""), date.today().year, date.today().year - 5, date.today().year + 5)

        if not form.is_valid():
            messages.error(request, "Please select at least one valid date.")
            return redirect(f"/calendar/?month={month}&year={year}")

        selected_dates = _parse_selected_dates(form.cleaned_data["selected_dates"])
        if not selected_dates:
            messages.error(request, "No valid dates were selected.")
            return redirect(f"/calendar/?month={month}&year={year}")

        if not profile.country:
            messages.error(request, "Your profile has no country assigned yet. Ask an admin.")
            return redirect(f"/calendar/?month={month}&year={year}")

        existing_rows = {
            row.date: row
            for row in DayOffRequest.objects.filter(user=request.user, date__in=selected_dates)
        }

        holiday_dates = set(
            PublicHoliday.objects.filter(country=profile.country, date__in=selected_dates).values_list("date", flat=True)
        )

        created_count = 0
        resubmitted_count = 0
        skipped_existing = 0
        skipped_holiday = 0
        skipped_weekend = 0

        for selected_date in selected_dates:
            if selected_date.weekday() >= 5:
                skipped_weekend += 1
                continue

            if selected_date in holiday_dates:
                skipped_holiday += 1
                continue

            existing = existing_rows.get(selected_date)

            if existing:
                if existing.status in [DayOffRequest.STATUS_PENDING, DayOffRequest.STATUS_APPROVED]:
                    skipped_existing += 1
                    continue

                existing.status = DayOffRequest.STATUS_PENDING
                existing.country = profile.country
                existing.reviewed_by = None
                existing.reviewed_at = None
                existing.note = ""
                existing.revoke_requested = False
                existing.revoke_requested_at = None
                existing.save(
                    update_fields=[
                        "status",
                        "country",
                        "reviewed_by",
                        "reviewed_at",
                        "note",
                        "revoke_requested",
                        "revoke_requested_at",
                        "updated_at",
                    ]
                )
                resubmitted_count += 1
                continue

            DayOffRequest.objects.create(
                user=request.user,
                country=profile.country,
                date=selected_date,
                status=DayOffRequest.STATUS_PENDING,
            )
            created_count += 1

        if created_count:
            messages.success(request, f"{created_count} day-off request(s) sent to admin for approval.")
        if resubmitted_count:
            messages.success(request, f"{resubmitted_count} rejected request(s) were re-submitted.")
        if skipped_existing:
            messages.info(request, f"{skipped_existing} date(s) were already pending/approved.")
        if skipped_holiday:
            messages.info(request, f"{skipped_holiday} date(s) are public holidays and were skipped.")
        if skipped_weekend:
            messages.info(request, f"{skipped_weekend} weekend date(s) were skipped.")

        return redirect(f"/calendar/?month={month}&year={year}")


class ManagerDashboardView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        today = date.today()
        month = _safe_int(request.GET.get("month", ""), today.month, 1, 12)
        year = _safe_int(request.GET.get("year", ""), today.year, today.year - 5, today.year + 5)
        month_start, month_end = _monthly_range(year, month)

        country_id_raw = request.GET.get("country", "")
        employee_id_raw = request.GET.get("employee", "")
        status_filter = request.GET.get("status", "")

        countries = Country.objects.all()
        employees = User.objects.filter(profile__isnull=False).select_related("profile").order_by("username")

        base_query = (
            DayOffRequest.objects.select_related("user", "country", "reviewed_by", "user__profile")
            .exclude(status=DayOffRequest.STATUS_CANCELLED)
        )

        selected_country = None
        if country_id_raw.isdigit():
            selected_country = Country.objects.filter(id=int(country_id_raw)).first()
            if selected_country:
                base_query = base_query.filter(country=selected_country)

        selected_employee = None
        if employee_id_raw.isdigit():
            selected_employee = employees.filter(id=int(employee_id_raw)).first()
            if selected_employee:
                base_query = base_query.filter(user=selected_employee)

        if status_filter in {
            DayOffRequest.STATUS_PENDING,
            DayOffRequest.STATUS_APPROVED,
            DayOffRequest.STATUS_REJECTED,
        }:
            base_query = base_query.filter(status=status_filter)

        month_query = base_query.filter(date__range=(month_start, month_end))
        counts_by_status = {
            row["status"]: row["count"] for row in month_query.values("status").annotate(count=Count("id"))
        }

        requests_for_list = month_query.order_by("-date", "user__username")[:500]

        requests_for_month = month_query

        holidays_query = PublicHoliday.objects.select_related("country")
        if selected_country:
            holidays_query = holidays_query.filter(country=selected_country)
        holidays_for_month = holidays_query.filter(date__range=(month_start, month_end))
        managed_holidays = holidays_query.order_by("date", "country__name", "name")[:120]

        employee_events = [
            {
                "id": row.id,
                "date": row.date.isoformat(),
                "status": row.status,
                "user_id": row.user_id,
                "employee": row.user.username,
                "country": row.country.code if row.country else "",
                "note": row.note or "",
                "revoke_requested": row.revoke_requested,
            }
            for row in requests_for_month
        ]
        holiday_events = [
            {
                "date": row.date.isoformat(),
                "name": row.name,
                "country": row.country.code,
            }
            for row in holidays_for_month
        ]

        pending_count = counts_by_status.get(DayOffRequest.STATUS_PENDING, 0)
        approved_count = counts_by_status.get(DayOffRequest.STATUS_APPROVED, 0)
        rejected_count = counts_by_status.get(DayOffRequest.STATUS_REJECTED, 0)
        revoke_requests_count = month_query.filter(
            status=DayOffRequest.STATUS_APPROVED,
            revoke_requested=True,
        ).count()

        active_panel = request.GET.get("panel", "requests")
        if active_panel not in {"requests", "add-country", "add-holiday", "revoke-holiday"}:
            active_panel = "requests"

        context = {
            "month": month,
            "year": year,
            "month_name": calendar.month_name[month],
            "month_options": list(enumerate(calendar.month_name))[1:],
            "requests": requests_for_list,
            "countries": countries,
            "employees": employees,
            "selected_country_id": int(country_id_raw) if country_id_raw.isdigit() else None,
            "selected_employee_id": int(employee_id_raw) if employee_id_raw.isdigit() else None,
            "can_select_mode": bool(selected_employee),
            "selected_status": status_filter,
            "employee_events_json": json.dumps(employee_events),
            "holiday_events_json": json.dumps(holiday_events),
            "country_form": CountryForm(),
            "holiday_form": PublicHolidayForm(),
            "managed_holidays": managed_holidays,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "revoke_requests_count": revoke_requests_count,
            "active_panel": active_panel,
        }

        return render(request, "timeoff/manager_dashboard.html", context)


class UserManagementView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        users = User.objects.filter(profile__isnull=False).select_related("profile", "profile__country").order_by("username")
        panel = request.GET.get("panel", "users")
        valid_panels = {"users", "create", "quick-update"}
        if panel not in valid_panels:
            panel = "users"

        quota_year = date.today().year
        user_rows = []
        for user in users:
            allowance = user.profile.annual_day_off_allowance or 30
            ledger = build_quota_ledger(
                user=user,
                allowance=allowance,
                year=quota_year,
                statuses=RESERVED_STATUSES,
            )
            user_rows.append(
                {
                    "user": user,
                    "allowance": allowance,
                    "current_left": ledger.current_left,
                    "carryover_left": ledger.carryover_left,
                    "total_left": ledger.total_left,
                }
            )

        profile_form_initial = {}
        selected_quick_user_id = request.GET.get("user", "")
        if panel == "quick-update" and selected_quick_user_id.isdigit():
            selected_quick_user = users.filter(id=int(selected_quick_user_id)).first()
            if selected_quick_user:
                selected_profile, _ = EmployeeProfile.objects.get_or_create(user=selected_quick_user)
                profile_form_initial = {
                    "user": selected_quick_user,
                    "country": selected_profile.country,
                    "role": selected_profile.role,
                    "annual_day_off_allowance": selected_profile.annual_day_off_allowance,
                }

        context = {
            "create_user_form": ManagerUserCreateForm(),
            "profile_form": EmployeeProfileUpdateForm(initial=profile_form_initial),
            "user_rows": user_rows,
            "total_users": len(user_rows),
            "quota_year": quota_year,
            "previous_year": quota_year - 1,
            "carryover_deadline": date(quota_year, 3, 31),
            "active_panel": panel,
            "selected_quick_user_id": int(selected_quick_user_id) if selected_quick_user_id.isdigit() else None,
        }
        return render(request, "timeoff/user_management.html", context)


class UserEditView(View):
    def get(self, request: HttpRequest, user_id: int) -> HttpResponse:
        selected_user = get_object_or_404(User, id=user_id)
        profile, _ = EmployeeProfile.objects.get_or_create(user=selected_user)
        form = EmployeeDirectUpdateForm(
            initial={
                "email": selected_user.email,
                "country": profile.country,
                "role": profile.role,
                "annual_day_off_allowance": profile.annual_day_off_allowance,
            }
        )
        context = {
            "selected_user": selected_user,
            "edit_form": form,
        }
        return render(request, "timeoff/user_edit.html", context)

    def post(self, request: HttpRequest, user_id: int) -> HttpResponse:
        selected_user = get_object_or_404(User, id=user_id)
        profile, _ = EmployeeProfile.objects.get_or_create(user=selected_user)
        form = EmployeeDirectUpdateForm(request.POST)

        if not form.is_valid():
            messages.error(request, "Could not update user. Check input values.")
            return render(
                request,
                "timeoff/user_edit.html",
                {
                    "selected_user": selected_user,
                    "edit_form": form,
                },
            )

        selected_user.email = form.cleaned_data.get("email", "")
        selected_user.save(update_fields=["email"])

        profile.country = form.cleaned_data["country"]
        profile.role = form.cleaned_data["role"]
        allowance = form.cleaned_data.get("annual_day_off_allowance")
        if allowance is not None:
            profile.annual_day_off_allowance = allowance
        elif not profile.annual_day_off_allowance:
            profile.annual_day_off_allowance = 30
        profile.save()

        messages.success(request, f"Updated {selected_user.username}.")
        return redirect(reverse("user_edit", kwargs={"user_id": selected_user.id}))


@login_required
@manager_required
def approve_request(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id)
    profile, _ = EmployeeProfile.objects.get_or_create(user=day_off_request.user)
    allowance = profile.annual_day_off_allowance

    approval_ledger = build_quota_ledger(
        user=day_off_request.user,
        allowance=allowance,
        year=day_off_request.date.year,
        statuses=[DayOffRequest.STATUS_APPROVED],
        exclude_request_id=day_off_request.id,
    )
    can_approve, _ = approval_ledger.try_allocate(day_off_request.date)
    if not can_approve:
        messages.error(
            request,
            f"Cannot approve {day_off_request.user.username} on {day_off_request.date}: "
            "no quota left for this period.",
        )
        return redirect(_safe_next_url(request, "manager_dashboard"))

    day_off_request.status = DayOffRequest.STATUS_APPROVED
    day_off_request.revoke_requested = False
    day_off_request.revoke_requested_at = None
    day_off_request.reviewed_by = request.user
    day_off_request.reviewed_at = timezone.now()
    day_off_request.save(
        update_fields=["status", "revoke_requested", "revoke_requested_at", "reviewed_by", "reviewed_at", "updated_at"]
    )
    messages.success(request, f"Approved {day_off_request.user.username} for {day_off_request.date}.")
    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def reject_request(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id)
    note = request.POST.get("note", "").strip()

    day_off_request.status = DayOffRequest.STATUS_REJECTED
    day_off_request.revoke_requested = False
    day_off_request.revoke_requested_at = None
    day_off_request.reviewed_by = request.user
    day_off_request.reviewed_at = timezone.now()
    day_off_request.note = note
    day_off_request.save(
        update_fields=[
            "status",
            "revoke_requested",
            "revoke_requested_at",
            "reviewed_by",
            "reviewed_at",
            "note",
            "updated_at",
        ]
    )
    messages.info(request, f"Rejected {day_off_request.user.username} for {day_off_request.date}.")
    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def revoke_approved_request(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id)
    if day_off_request.status != DayOffRequest.STATUS_APPROVED:
        messages.error(request, "Only approved requests can be revoked.")
        return redirect(_safe_next_url(request, "manager_dashboard"))

    day_off_request.status = DayOffRequest.STATUS_CANCELLED
    day_off_request.revoke_requested = False
    day_off_request.revoke_requested_at = None
    day_off_request.reviewed_by = request.user
    day_off_request.reviewed_at = timezone.now()
    day_off_request.note = "Approved day revoked by admin."
    day_off_request.save(
        update_fields=[
            "status",
            "revoke_requested",
            "revoke_requested_at",
            "reviewed_by",
            "reviewed_at",
            "note",
            "updated_at",
        ]
    )
    messages.info(request, f"Revoked approved day for {day_off_request.user.username} on {day_off_request.date}.")
    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def add_country(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    form = CountryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Country created.")
    else:
        messages.error(request, "Could not create country. Check input values.")

    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def add_holiday(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    form = PublicHolidayForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Public holiday created.")
    else:
        messages.error(request, "Could not create holiday. Check input values.")

    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def delete_holiday(request: HttpRequest, holiday_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    holiday = get_object_or_404(PublicHoliday, id=holiday_id)
    holiday_label = f"{holiday.country.code} {holiday.name} ({holiday.date})"
    holiday.delete()
    messages.info(request, f"Revoked public holiday: {holiday_label}.")
    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def update_employee_profile(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(f"{reverse('user_management')}?panel=quick-update")

    form = EmployeeProfileUpdateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Could not update employee settings. Check input values.")
        selected_user_raw = request.POST.get("user", "")
        user_query = f"&user={selected_user_raw}" if selected_user_raw.isdigit() else ""
        return redirect(f"{reverse('user_management')}?panel=quick-update{user_query}")

    selected_user = form.cleaned_data["user"]
    profile, _ = EmployeeProfile.objects.get_or_create(user=selected_user)
    profile.country = form.cleaned_data["country"]
    profile.role = form.cleaned_data["role"]
    allowance = form.cleaned_data.get("annual_day_off_allowance")
    if allowance is not None:
        profile.annual_day_off_allowance = allowance
    elif not profile.annual_day_off_allowance:
        profile.annual_day_off_allowance = 30
    profile.save()

    messages.success(
        request,
        f"Updated {selected_user.username}: allowance={profile.annual_day_off_allowance}, "
        f"role={profile.role}, carryover=automatic.",
    )
    return redirect(f"{reverse('user_management')}?panel=quick-update&user={selected_user.id}")


@login_required
@manager_required
def create_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(f"{reverse('user_management')}?panel=create")

    form = ManagerUserCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Could not create user. Check username/password fields.")
        return redirect(f"{reverse('user_management')}?panel=create")

    created_user = form.save()
    messages.success(request, f"User '{created_user.username}' created successfully.")
    return redirect(f"{reverse('user_management')}?panel=users")


@login_required
def revoke_own_request(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("employee_calendar")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id, user=request.user)

    if day_off_request.status != DayOffRequest.STATUS_PENDING:
        messages.error(request, "Only pending requests can be revoked.")
        return redirect(_safe_next_url(request, "employee_calendar"))

    day_off_request.status = DayOffRequest.STATUS_CANCELLED
    day_off_request.revoke_requested = False
    day_off_request.revoke_requested_at = None
    day_off_request.reviewed_by = None
    day_off_request.reviewed_at = timezone.now()
    day_off_request.note = "Cancelled by employee."
    day_off_request.save(
        update_fields=[
            "status",
            "revoke_requested",
            "revoke_requested_at",
            "reviewed_by",
            "reviewed_at",
            "note",
            "updated_at",
        ]
    )
    messages.info(request, f"Revoked request for {day_off_request.date}.")
    return redirect(_safe_next_url(request, "employee_calendar"))


@login_required
def request_revoke_approved(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("employee_calendar")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id, user=request.user)

    if day_off_request.status != DayOffRequest.STATUS_APPROVED:
        messages.error(request, "Only approved requests can have revoke request.")
        return redirect(_safe_next_url(request, "employee_calendar"))

    if day_off_request.revoke_requested:
        messages.info(request, f"Revoke already requested for {day_off_request.date}.")
        return redirect(_safe_next_url(request, "employee_calendar"))

    day_off_request.revoke_requested = True
    day_off_request.revoke_requested_at = timezone.now()
    day_off_request.note = "Employee requested revoke of approved day."
    day_off_request.save(update_fields=["revoke_requested", "revoke_requested_at", "note", "updated_at"])
    messages.info(request, f"Revoke request sent for approved day {day_off_request.date}.")
    return redirect(_safe_next_url(request, "employee_calendar"))


@login_required
def bulk_manage_own_requests(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("employee_calendar")

    action = request.POST.get("action", "").strip()
    raw_request_ids = _parse_json_list(request.POST.get("request_ids", ""))
    raw_checked_dates = _parse_json_list(request.POST.get("checked_dates", ""))

    request_ids = []
    for raw_id in raw_request_ids:
        try:
            request_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    request_ids = sorted(set(request_ids))

    checked_dates = []
    for raw_date in raw_checked_dates:
        if not isinstance(raw_date, str):
            continue
        try:
            checked_dates.append(date.fromisoformat(raw_date))
        except ValueError:
            continue
    checked_dates = sorted(set(checked_dates))
    checked_dates_count = len(checked_dates)

    if action == "request_approval":
        if not checked_dates:
            messages.info(request, "No days selected in select mode.")
            return redirect(_safe_next_url(request, "employee_calendar"))

        profile, _ = EmployeeProfile.objects.get_or_create(user=request.user)
        if not profile.country:
            messages.error(request, "Your profile has no country assigned yet. Ask an admin.")
            return redirect(_safe_next_url(request, "employee_calendar"))

        existing_rows = {
            row.date: row
            for row in DayOffRequest.objects.filter(user=request.user, date__in=checked_dates)
        }
        holiday_dates = set(
            PublicHoliday.objects.filter(country=profile.country, date__in=checked_dates).values_list("date", flat=True)
        )

        created_count = 0
        resubmitted_count = 0
        skipped_existing = 0
        skipped_holiday = 0
        skipped_weekend = 0

        for selected_date in checked_dates:
            if selected_date.weekday() >= 5:
                skipped_weekend += 1
                continue
            if selected_date in holiday_dates:
                skipped_holiday += 1
                continue

            existing = existing_rows.get(selected_date)
            if existing:
                if existing.status in [DayOffRequest.STATUS_PENDING, DayOffRequest.STATUS_APPROVED]:
                    skipped_existing += 1
                    continue

                existing.status = DayOffRequest.STATUS_PENDING
                existing.country = profile.country
                existing.reviewed_by = None
                existing.reviewed_at = None
                existing.note = ""
                existing.revoke_requested = False
                existing.revoke_requested_at = None
                existing.save(
                    update_fields=[
                        "status",
                        "country",
                        "reviewed_by",
                        "reviewed_at",
                        "note",
                        "revoke_requested",
                        "revoke_requested_at",
                        "updated_at",
                    ]
                )
                resubmitted_count += 1
                continue

            DayOffRequest.objects.create(
                user=request.user,
                country=profile.country,
                date=selected_date,
                status=DayOffRequest.STATUS_PENDING,
            )
            created_count += 1

        if created_count:
            messages.success(request, f"Requested approval for {created_count} day(s).")
        if resubmitted_count:
            messages.success(request, f"Re-requested approval for {resubmitted_count} day(s).")
        if skipped_existing:
            messages.info(request, f"{skipped_existing} day(s) were already pending/approved.")
        if skipped_holiday:
            messages.info(request, f"{skipped_holiday} public holiday day(s) were skipped.")
        if skipped_weekend:
            messages.info(request, f"{skipped_weekend} weekend day(s) were skipped.")
        return redirect(_safe_next_url(request, "employee_calendar"))

    if not request_ids and checked_dates:
        request_ids = sorted(
            set(DayOffRequest.objects.filter(user=request.user, date__in=checked_dates).values_list("id", flat=True))
        )

    if not request_ids:
        if checked_dates_count:
            messages.info(request, "Selected days had no request records for this action.")
        else:
            messages.info(request, "No days selected in select mode.")
        return redirect(_safe_next_url(request, "employee_calendar"))

    owned_requests = {
        row.id: row
        for row in DayOffRequest.objects.filter(
            id__in=request_ids,
            user=request.user,
        )
    }

    processed = 0
    ignored = max(checked_dates_count - len(owned_requests), 0)
    now = timezone.now()

    for request_id in request_ids:
        row = owned_requests.get(request_id)
        if not row:
            continue

        if action == "revoke_pending":
            if row.status != DayOffRequest.STATUS_PENDING:
                ignored += 1
                continue
            row.status = DayOffRequest.STATUS_CANCELLED
            row.revoke_requested = False
            row.revoke_requested_at = None
            row.reviewed_by = None
            row.reviewed_at = now
            row.note = "Cancelled by employee (bulk manage)."
            row.save(
                update_fields=[
                    "status",
                    "revoke_requested",
                    "revoke_requested_at",
                    "reviewed_by",
                    "reviewed_at",
                    "note",
                    "updated_at",
                ]
            )
            processed += 1
            continue

        if action == "request_revoke_approved":
            if row.status != DayOffRequest.STATUS_APPROVED or row.revoke_requested:
                ignored += 1
                continue
            row.revoke_requested = True
            row.revoke_requested_at = now
            row.note = "Employee requested revoke of approved day (bulk manage)."
            row.save(update_fields=["revoke_requested", "revoke_requested_at", "note", "updated_at"])
            processed += 1
            continue

        ignored += 1

    if action == "revoke_pending":
        if processed:
            messages.info(request, f"Revoked {processed} pending request(s).")
    elif action == "request_revoke_approved":
        if processed:
            messages.info(request, f"Sent {processed} approved-day revoke request(s) to admin.")
    else:
        messages.error(request, "Unknown bulk action.")

    if ignored:
        messages.info(request, f"Ignored {ignored} day(s) that did not match this action.")

    return redirect(_safe_next_url(request, "employee_calendar"))


@login_required
@manager_required
def approve_revoke_request(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id)
    if day_off_request.status != DayOffRequest.STATUS_APPROVED or not day_off_request.revoke_requested:
        messages.error(request, "This request has no pending revoke request.")
        return redirect(_safe_next_url(request, "manager_dashboard"))

    day_off_request.status = DayOffRequest.STATUS_CANCELLED
    day_off_request.revoke_requested = False
    day_off_request.revoke_requested_at = None
    day_off_request.reviewed_by = request.user
    day_off_request.reviewed_at = timezone.now()
    day_off_request.note = "Approved-day revoke approved by admin."
    day_off_request.save(
        update_fields=[
            "status",
            "revoke_requested",
            "revoke_requested_at",
            "reviewed_by",
            "reviewed_at",
            "note",
            "updated_at",
        ]
    )
    messages.success(request, f"Approved revoke for {day_off_request.user.username} on {day_off_request.date}.")
    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def reject_revoke_request(request: HttpRequest, request_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    day_off_request = get_object_or_404(DayOffRequest, id=request_id)
    if day_off_request.status != DayOffRequest.STATUS_APPROVED or not day_off_request.revoke_requested:
        messages.error(request, "This request has no pending revoke request.")
        return redirect(_safe_next_url(request, "manager_dashboard"))

    note = request.POST.get("note", "").strip()
    day_off_request.revoke_requested = False
    day_off_request.revoke_requested_at = None
    day_off_request.reviewed_by = request.user
    day_off_request.reviewed_at = timezone.now()
    day_off_request.note = note or "Approved-day revoke request rejected by admin."
    day_off_request.save(
        update_fields=[
            "revoke_requested",
            "revoke_requested_at",
            "reviewed_by",
            "reviewed_at",
            "note",
            "updated_at",
        ]
    )
    messages.info(request, f"Kept approved day for {day_off_request.user.username} on {day_off_request.date}.")
    return redirect(_safe_next_url(request, "manager_dashboard"))


@login_required
@manager_required
def bulk_review_requests(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("manager_dashboard")

    action = request.POST.get("action", "").strip()
    employee_id_raw = request.POST.get("employee_id", "").strip()
    raw_request_ids = _parse_json_list(request.POST.get("request_ids", ""))
    raw_checked_dates = _parse_json_list(request.POST.get("checked_dates", ""))

    if not employee_id_raw.isdigit():
        messages.error(request, "Select exactly one employee to use admin select mode.")
        return redirect(_safe_next_url(request, "manager_dashboard"))
    employee_id = int(employee_id_raw)

    request_ids = []
    for raw_id in raw_request_ids:
        try:
            request_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    request_ids = sorted(set(request_ids))

    checked_dates = []
    for raw_date in raw_checked_dates:
        if not isinstance(raw_date, str):
            continue
        try:
            checked_dates.append(date.fromisoformat(raw_date))
        except ValueError:
            continue
    checked_dates = sorted(set(checked_dates))

    if not request_ids and checked_dates:
        request_ids = sorted(
            set(
                DayOffRequest.objects.filter(
                    user_id=employee_id,
                    date__in=checked_dates,
                ).values_list("id", flat=True)
            )
        )

    if not request_ids:
        messages.info(request, "No eligible requests selected.")
        return redirect(_safe_next_url(request, "manager_dashboard"))

    rows = list(
        DayOffRequest.objects.filter(
            id__in=request_ids,
            user_id=employee_id,
        ).select_related("user")
    )
    if not rows:
        messages.info(request, "Selected requests were ignored.")
        return redirect(_safe_next_url(request, "manager_dashboard"))

    processed = 0
    ignored = 0
    blocked_quota = 0
    skipped_locked_days = 0
    now = timezone.now()
    seen_ids = set()
    row_dates = [row.date for row in rows]
    row_country_ids = sorted({row.country_id for row in rows if row.country_id})
    holiday_pairs = set(
        PublicHoliday.objects.filter(
            country_id__in=row_country_ids,
            date__in=row_dates,
        ).values_list("country_id", "date")
    )

    for row in rows:
        if row.id in seen_ids:
            continue
        seen_ids.add(row.id)

        if row.date.weekday() >= 5:
            skipped_locked_days += 1
            continue
        if row.country_id and (row.country_id, row.date) in holiday_pairs:
            skipped_locked_days += 1
            continue

        if action == "approve_pending":
            if row.status != DayOffRequest.STATUS_PENDING:
                ignored += 1
                continue
            profile, _ = EmployeeProfile.objects.get_or_create(user=row.user)
            allowance = profile.annual_day_off_allowance
            approval_ledger = build_quota_ledger(
                user=row.user,
                allowance=allowance,
                year=row.date.year,
                statuses=[DayOffRequest.STATUS_APPROVED],
                exclude_request_id=row.id,
            )
            can_approve, _ = approval_ledger.try_allocate(row.date)
            if not can_approve:
                blocked_quota += 1
                continue
            row.status = DayOffRequest.STATUS_APPROVED
            row.revoke_requested = False
            row.revoke_requested_at = None
            row.reviewed_by = request.user
            row.reviewed_at = now
            row.save(
                update_fields=[
                    "status",
                    "revoke_requested",
                    "revoke_requested_at",
                    "reviewed_by",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            processed += 1
            continue

        if action == "reject_pending":
            if row.status != DayOffRequest.STATUS_PENDING:
                ignored += 1
                continue
            row.status = DayOffRequest.STATUS_REJECTED
            row.revoke_requested = False
            row.revoke_requested_at = None
            row.reviewed_by = request.user
            row.reviewed_at = now
            row.note = "Rejected by admin (bulk)."
            row.save(
                update_fields=[
                    "status",
                    "revoke_requested",
                    "revoke_requested_at",
                    "reviewed_by",
                    "reviewed_at",
                    "note",
                    "updated_at",
                ]
            )
            processed += 1
            continue

        if action == "approve_revoke":
            if row.status != DayOffRequest.STATUS_APPROVED or not row.revoke_requested:
                ignored += 1
                continue
            row.status = DayOffRequest.STATUS_CANCELLED
            row.revoke_requested = False
            row.revoke_requested_at = None
            row.reviewed_by = request.user
            row.reviewed_at = now
            row.note = "Approved-day revoke approved by admin (bulk)."
            row.save(
                update_fields=[
                    "status",
                    "revoke_requested",
                    "revoke_requested_at",
                    "reviewed_by",
                    "reviewed_at",
                    "note",
                    "updated_at",
                ]
            )
            processed += 1
            continue

        if action == "revoke_approved":
            if row.status != DayOffRequest.STATUS_APPROVED:
                ignored += 1
                continue
            row.status = DayOffRequest.STATUS_CANCELLED
            row.revoke_requested = False
            row.revoke_requested_at = None
            row.reviewed_by = request.user
            row.reviewed_at = now
            row.note = "Approved day revoked by admin (bulk)."
            row.save(
                update_fields=[
                    "status",
                    "revoke_requested",
                    "revoke_requested_at",
                    "reviewed_by",
                    "reviewed_at",
                    "note",
                    "updated_at",
                ]
            )
            processed += 1
            continue

        if action == "reject_revoke":
            if row.status != DayOffRequest.STATUS_APPROVED or not row.revoke_requested:
                ignored += 1
                continue
            row.revoke_requested = False
            row.revoke_requested_at = None
            row.reviewed_by = request.user
            row.reviewed_at = now
            row.note = "Approved-day revoke request rejected by admin (bulk)."
            row.save(
                update_fields=[
                    "revoke_requested",
                    "revoke_requested_at",
                    "reviewed_by",
                    "reviewed_at",
                    "note",
                    "updated_at",
                ]
            )
            processed += 1
            continue

        ignored += 1

    if action == "approve_pending":
        messages.success(request, f"Approved {processed} pending request(s).")
    elif action == "reject_pending":
        messages.info(request, f"Rejected {processed} pending request(s).")
    elif action == "approve_revoke":
        messages.success(request, f"Approved {processed} revoke request(s).")
    elif action == "revoke_approved":
        messages.info(request, f"Revoked {processed} approved day(s).")
    elif action == "reject_revoke":
        messages.info(request, f"Kept approved status for {processed} request(s).")
    else:
        messages.error(request, "Unknown bulk action.")

    if blocked_quota:
        messages.warning(request, f"{blocked_quota} request(s) could not be approved due to quota limits.")
    if skipped_locked_days:
        messages.info(request, f"Ignored {skipped_locked_days} weekend/public-holiday day(s).")
    if ignored:
        messages.info(request, f"Ignored {ignored} request(s) that do not match this action.")

    return redirect(_safe_next_url(request, "manager_dashboard"))


employee_calendar = login_required(EmployeeCalendarView.as_view())
manager_dashboard = login_required(manager_required(ManagerDashboardView.as_view()))
user_management = login_required(manager_required(UserManagementView.as_view()))
user_edit = login_required(manager_required(UserEditView.as_view()))
