from django.contrib.auth.models import User
from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=2, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class PublicHoliday(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="holidays")
    name = models.CharField(max_length=150)
    date = models.DateField()

    class Meta:
        ordering = ["date", "country__name", "name"]
        unique_together = [("country", "date", "name")]

    def __str__(self) -> str:
        return f"{self.country.code} - {self.name} ({self.date})"


class EmployeeProfile(models.Model):
    ROLE_EMPLOYEE = "employee"
    ROLE_MANAGER = "manager"
    ROLE_CHOICES = [
        (ROLE_EMPLOYEE, "Employee"),
        (ROLE_MANAGER, "Admin"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_EMPLOYEE)
    annual_day_off_allowance = models.PositiveIntegerField(default=30)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user.username} profile"


class DayOffRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="day_off_requests")
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name="day_off_requests")
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note = models.CharField(max_length=255, blank=True)
    revoke_requested = models.BooleanField(default=False)
    revoke_requested_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_day_off_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = [("user", "date")]

    def __str__(self) -> str:
        return f"{self.user.username} {self.date} ({self.status})"


class UserCarryoverOverride(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="carryover_overrides")
    year = models.PositiveIntegerField()
    days = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username", "-year"]
        unique_together = [("user", "year")]

    def __str__(self) -> str:
        return f"{self.user.username} carryover {self.year}: {self.days}"
