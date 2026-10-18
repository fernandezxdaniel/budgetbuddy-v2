# Budget Buddy

Budget Buddy is a Flask application that serves its frontend and stores each
account's budget plan in SQLite for local development or PostgreSQL in
production.

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

The application creates its PostgreSQL tables at startup. User accounts and
plans are isolated by the authenticated account ID; an existing SQLite database
is not automatically copied to PostgreSQL, so users must create accounts again
after switching databases.
