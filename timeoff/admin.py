from django.contrib import admin

from .models import Country, DayOffRequest, EmployeeProfile, PublicHoliday, UserCarryoverOverride


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "date")
    list_filter = ("country", "date")
    search_fields = ("name",)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "country", "annual_day_off_allowance")
    list_filter = ("role", "country")
    search_fields = ("user__username", "user__email")


@admin.register(DayOffRequest)
class DayOffRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "status", "revoke_requested", "country", "reviewed_by", "reviewed_at")
    list_filter = ("status", "country", "date")
    search_fields = ("user__username", "note")


@admin.register(UserCarryoverOverride)
class UserCarryoverOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "year", "days", "updated_at")
    list_filter = ("year",)
    search_fields = ("user__username",)
