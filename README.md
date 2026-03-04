# Calendario

Lightweight Django app for managing employee days off with admin approval.

## Features

- Employees see only their own day-off requests.
- Employees can revoke their own pending requests if made by mistake.
- Employees can request revoke for already approved days; admins can approve or deny those revoke requests.
- Employee calendar includes `Manage Mode` with day checkboxes for bulk actions (revoke pending / request revoke approved), while ignoring incompatible day types automatically.
- Admin users can review all requests and approve/reject.
- Default annual allowance is 30 days per employee.
- Countries + public holidays are managed in-app by admins.
- Admins can update employee allowance/country/role from the `User Management` tab.
- Admins can create users from the `User Management` tab.
- Usernames in `User Management` are clickable and open a dedicated edit page.
- Admins can set/clear manual carryover override days per user/year.
- Admins can revoke (delete) public holidays from the admin dashboard.
- Seeded defaults include Germany (`DE`) and Czech Republic (`CZ`) holidays for 2026.
- Calendar filtering for admins by country, employee, status, and date range.
- Annual allowance is Jan 1 - Dec 31, with automatic carryover from previous year.
- Carryover days are usable only until March 31 of the following year (default rule).
- Built-in login, logout, password change, and password reset flows.
- SQLite database by default.

## Quick Start

1. Create virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Create first admin user:

```bash
python manage.py create_manager --username admin
```

5. Start server:

```bash
python manage.py runserver
```

6. Open app:

- App: `http://127.0.0.1:8000/`
- Admin dashboard: `http://127.0.0.1:8000/admin/`

## Docker Compose (Server)

Run Calendario on a server with Docker:

1. Build and start:

```bash
docker compose up -d --build
```

2. Open app:

- App: `http://<server-ip>:8080/`
- Admin dashboard: `http://<server-ip>:8080/admin/`

3. Create first manager user:

```bash
docker compose exec web python manage.py create_manager --username admin
```

4. Logs and stop:

```bash
docker compose logs -f web
docker compose down
```

Notes:

- SQLite is persisted in Docker volume `calendario_data` at `/app/data/db.sqlite3`.
- Migrations run automatically on container start.
- To change exposed port, set env before start:

```bash
export CALENDARIO_PORT=8090
docker compose up -d --build
```

## Role Setup

- Each user gets an `EmployeeProfile` automatically.
- Set profile `role` to `manager` for admin access.
- Set `country` and `annual_day_off_allowance` per user profile.

## Notes

- Password reset emails use Django console backend (printed in terminal in development).
- Public holidays are stored as date entries and can be extended by admins.
- Django built-in admin route is disabled to keep a single admin interface.

## LDAP Login (Optional)

You can enable LDAP authentication while keeping local Django login as fallback.

1. Install LDAP packages:

```bash
pip install -r requirements-ldap.txt
```

2. Add LDAP environment variables (copy from [ldap.env.example](/Users/benjaminvlaisavljevikj/calendario/ldap.env.example)):

```bash
export ENABLE_LDAP_AUTH=true
export AUTH_LDAP_SERVER_URI="ldap://ldap.example.com:389"
export AUTH_LDAP_BIND_DN="cn=svc_bind,ou=service,dc=example,dc=com"
export AUTH_LDAP_BIND_PASSWORD="replace_me"
export AUTH_LDAP_USER_BASE_DN="ou=users,dc=example,dc=com"
export AUTH_LDAP_USER_FILTER="(uid=%(user)s)"
```

3. Optional admin mapping via LDAP group:

```bash
export AUTH_LDAP_GROUP_BASE_DN="ou=groups,dc=example,dc=com"
export AUTH_LDAP_MANAGER_GROUP_DN="cn=calendar-managers,ou=groups,dc=example,dc=com"
```

When `AUTH_LDAP_MANAGER_GROUP_DN` matches, user gets `is_staff=True` and will have admin access in Calendario.

### Common username filters

- Active Directory: `AUTH_LDAP_USER_FILTER="(sAMAccountName=%(user)s)"`
- OpenLDAP: `AUTH_LDAP_USER_FILTER="(uid=%(user)s)"`
