"""One-time local setup. Creates only new, dedicated OpsPilot databases and a role."""

import os
import secrets
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
ROLE = "opspilot_app"
DATABASES = ("opspilot_dev", "opspilot_foundation_test")


def main() -> None:
    if ENV_PATH.exists():
        raise SystemExit("backend/.env already exists; no changes made.")
    # Existing administrator credentials use libpq's PGUSER/PGPASSWORD/.pgpass handling.
    host = os.environ.get("PGHOST", "127.0.0.1")
    port = int(os.environ.get("PGPORT", "5432"))
    if host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("This helper only supports a local PostgreSQL server.")
    password = secrets.token_urlsafe(32)
    with psycopg.connect(dbname="postgres", host=host, port=port, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone():
            raise SystemExit("OpsPilot role already exists; no changes made.")
        if admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = ANY(%s)", (list(DATABASES),)
        ).fetchone():
            raise SystemExit("An OpsPilot database already exists; no changes made.")
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                sql.Identifier(ROLE), sql.Literal(password)
            )
        )
        # CREATE DATABASE cannot run inside a PostgreSQL transaction.
        for database in DATABASES:
            admin.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database), sql.Identifier(ROLE)
                )
            )
    # Exclusive create and owner-only permissions. Never print the generated password/URLs.
    descriptor = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as env_file:
        base = f"postgresql+psycopg://{ROLE}:{password}@{host}:{port}/"
        env_file.write(f"DATABASE_URL={base}{DATABASES[0]}\n")
        env_file.write("PUBLIC_ORIGIN=https://localhost:3000\n")
        env_file.write(f"TEST_DATABASE_URL={base}{DATABASES[1]}\n")
    print("Created dedicated development/test databases and backend/.env (mode 0600).")
    print("No migrations have been applied. Existing databases were not modified.")


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error:
        raise SystemExit(
            "Local database setup failed. Check server/admin access; existing work was not reset. "
            "Setup may have created a role/database before failure; inspect before retrying."
        ) from None
