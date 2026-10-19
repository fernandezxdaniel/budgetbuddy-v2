# Budget Buddy

Budget Buddy is a Flask application that serves its frontend and stores each
account's independent budget periods in SQLite for local development or
PostgreSQL in production. Each exact start/end date range has its own
50/30/20 budgets and actual entries; dated income is included in every range
that contains its date. Selecting another period does not replace or clear
existing data.

Choose a start date and end date on the calendar to open a period. Choosing the
same two dates later reopens that period; a new date range starts empty. Income
and 50/30/20 targets are calculated for the selected period. **Reset this
period** clears only that range, after confirmation.

Income is recorded as dated transactions and summed when it falls inside the
selected range. Analytics uses the segment tree to total daily income and
needs/wants actuals into a fixed six-month cash-flow trend, with monthly
averages and a selectable month-to-month expense comparison. The current month
is a month-to-date total; expenses include needs and wants, while savings remain
a separate 50/30/20 category.

## Run locally

From the repository root, install the backend dependencies and start Flask:

```powershell
py -m pip install -r backend/requirements.txt
$env:SECRET_KEY = "replace-this-with-a-long-random-value"
py backend\app.py
```

Open <http://127.0.0.1:5000>. Without `DATABASE_URL`, the app creates and uses
`backend/budgetbuddy.db`. For local PostgreSQL, set `DATABASE_URL` to its
connection string before starting the app.

Run the backend checks from the backend directory:

```powershell
py test_backend.py
```

## Deploy to GitHub and Render

1. Push this repository to GitHub.
2. In Render, choose **New + → Blueprint**, connect the GitHub repository, and
   apply the `render.yaml` configuration. It creates the Flask web service and
   PostgreSQL database, then supplies `DATABASE_URL` and a generated `SECRET_KEY`.
3. Wait for the Render deploy to become **Live**, then open the service URL.
   Check `<your-service-url>/api/health`; it should return `{"ok":true,"database":"postgresql"}`.

For an existing Render service instead of a Blueprint, set its root directory to
`backend`, build command to `pip install -r requirements.txt`, and start command
to `gunicorn app:app`. Add `DATABASE_URL` from the PostgreSQL service and a
stable, private `SECRET_KEY` environment variable. Do not commit either secret.

The application creates and upgrades its PostgreSQL tables at startup. Existing
single-plan data in a database is copied into its matching period the first
time the new schema starts; other periods are kept separately. User accounts
and periods are isolated by the authenticated account ID. An existing SQLite
database is not automatically copied to PostgreSQL, so users must create
accounts again after switching databases.
