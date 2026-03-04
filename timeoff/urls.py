from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("calendar/", views.employee_calendar, name="employee_calendar"),
    path("calendar/requests/<int:request_id>/revoke/", views.revoke_own_request, name="revoke_own_request"),
    path("calendar/requests/bulk-manage/", views.bulk_manage_own_requests, name="bulk_manage_own_requests"),
    path(
        "calendar/requests/<int:request_id>/request-revoke/",
        views.request_revoke_approved,
        name="request_revoke_approved",
    ),
    path("admin/", views.manager_dashboard, name="manager_dashboard"),
    path("admin/user-management/", views.user_management, name="user_management"),
    path("admin/user-management/users/<int:user_id>/", views.user_edit, name="user_edit"),
    path("admin/requests/<int:request_id>/approve/", views.approve_request, name="approve_request"),
    path("admin/requests/<int:request_id>/reject/", views.reject_request, name="reject_request"),
    path("admin/requests/<int:request_id>/revoke-approved/", views.revoke_approved_request, name="revoke_approved_request"),
    path("admin/requests/bulk-review/", views.bulk_review_requests, name="bulk_review_requests"),
    path("admin/requests/<int:request_id>/revoke/approve/", views.approve_revoke_request, name="approve_revoke_request"),
    path("admin/requests/<int:request_id>/revoke/reject/", views.reject_revoke_request, name="reject_revoke_request"),
    path("admin/countries/add/", views.add_country, name="add_country"),
    path("admin/holidays/add/", views.add_holiday, name="add_holiday"),
    path("admin/holidays/<int:holiday_id>/delete/", views.delete_holiday, name="delete_holiday"),
    path("admin/users/add/", views.create_user, name="create_user"),
    path("admin/employees/update/", views.update_employee_profile, name="update_employee_profile"),
]
