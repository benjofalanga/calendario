import json
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from timeoff.models import Country, DayOffRequest, EmployeeProfile, UserCarryoverOverride
from timeoff.quota import build_quota_ledger


class QaFlowTestCase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="qa_manager", password="Pass12345!")
        self.employee = User.objects.create_user(username="qa_employee", password="Pass12345!")

        self.country = Country.objects.filter(code="DE").first()
        if not self.country:
            self.country = Country.objects.create(name="Germany", code="DE")

        manager_profile = self.manager.profile
        manager_profile.role = EmployeeProfile.ROLE_MANAGER
        manager_profile.country = self.country
        manager_profile.annual_day_off_allowance = 30
        manager_profile.save()

        employee_profile = self.employee.profile
        employee_profile.role = EmployeeProfile.ROLE_EMPLOYEE
        employee_profile.country = self.country
        employee_profile.annual_day_off_allowance = 30
        employee_profile.save()

        override, _ = UserCarryoverOverride.objects.get_or_create(user=self.employee, year=2026)
        override.days = 15
        override.save()

        self.employee_client = Client()
        self.manager_client = Client()
        self.employee_client.force_login(self.employee)
        self.manager_client.force_login(self.manager)

    def test_end_to_end_request_approve_revoke_and_quota(self):
        selected_dates = ["2026-03-02", "2026-03-03", "2026-03-07", "2026-04-03"]
        response = self.employee_client.post(
            reverse("employee_calendar"),
            {
                "selected_dates": json.dumps(selected_dates),
                "month": "3",
                "year": "2026",
            },
        )
        self.assertEqual(response.status_code, 302)

        requests = DayOffRequest.objects.filter(user=self.employee).order_by("date")
        self.assertEqual(requests.count(), 2)
        self.assertEqual(
            list(requests.values_list("date", flat=True)),
            [
                date(2026, 3, 2),
                date(2026, 3, 3),
            ],
        )
        self.assertEqual(set(requests.values_list("status", flat=True)), {DayOffRequest.STATUS_PENDING})

        req_0302 = DayOffRequest.objects.get(user=self.employee, date="2026-03-02")
        response = self.manager_client.post(reverse("approve_request", kwargs={"request_id": req_0302.id}))
        self.assertEqual(response.status_code, 302)
        req_0302.refresh_from_db()
        self.assertEqual(req_0302.status, DayOffRequest.STATUS_APPROVED)

        response = self.employee_client.post(reverse("request_revoke_approved", kwargs={"request_id": req_0302.id}))
        self.assertEqual(response.status_code, 302)
        req_0302.refresh_from_db()
        self.assertTrue(req_0302.revoke_requested)

        response = self.manager_client.post(reverse("approve_revoke_request", kwargs={"request_id": req_0302.id}))
        self.assertEqual(response.status_code, 302)
        req_0302.refresh_from_db()
        self.assertEqual(req_0302.status, DayOffRequest.STATUS_CANCELLED)
        self.assertFalse(req_0302.revoke_requested)

        response = self.employee_client.post(
            reverse("bulk_manage_own_requests"),
            {
                "action": "request_approval",
                "checked_dates": json.dumps(["2026-03-04", "2026-04-07"]),
                "request_ids": json.dumps([]),
            },
        )
        self.assertEqual(response.status_code, 302)

        req_0304 = DayOffRequest.objects.get(user=self.employee, date="2026-03-04")
        response = self.employee_client.post(
            reverse("bulk_manage_own_requests"),
            {
                "action": "revoke_pending",
                "checked_dates": json.dumps(["2026-03-04"]),
                "request_ids": json.dumps([req_0304.id]),
            },
        )
        self.assertEqual(response.status_code, 302)
        req_0304.refresh_from_db()
        self.assertEqual(req_0304.status, DayOffRequest.STATUS_CANCELLED)

        req_0407 = DayOffRequest.objects.get(user=self.employee, date="2026-04-07")
        response = self.manager_client.post(reverse("approve_request", kwargs={"request_id": req_0407.id}))
        self.assertEqual(response.status_code, 302)
        req_0407.refresh_from_db()
        self.assertEqual(req_0407.status, DayOffRequest.STATUS_APPROVED)

        approved_count = DayOffRequest.objects.filter(
            user=self.employee,
            status=DayOffRequest.STATUS_APPROVED,
            date__year=2026,
        ).count()
        pending_count = DayOffRequest.objects.filter(
            user=self.employee,
            status=DayOffRequest.STATUS_PENDING,
            date__year=2026,
        ).count()

        ledger = build_quota_ledger(
            user=self.employee,
            allowance=self.employee.profile.annual_day_off_allowance,
            year=2026,
            statuses=[DayOffRequest.STATUS_APPROVED],
        )

        self.assertEqual(approved_count, 1)
        self.assertEqual(pending_count, 1)
        self.assertEqual(ledger.carryover_start, 15)
        self.assertEqual(ledger.carryover_used, 0)
        self.assertEqual(ledger.current_used, 1)
        self.assertEqual(ledger.total_left, 44)
