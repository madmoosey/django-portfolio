"""
Management command: wait_for_db

Blocks until the PostgreSQL database is available.
Used in Docker entrypoint to handle container startup ordering
(Django container may start before PostgreSQL is ready).
"""

import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Wait for the database to be available before proceeding."""

    help = "Blocks execution until the database is available."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="Maximum seconds to wait for the database (default: 30).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Seconds between retry attempts (default: 1.0).",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]
        start_time = time.monotonic()

        self.stdout.write(self.style.WARNING("Waiting for database..."))

        while True:
            elapsed = time.monotonic() - start_time

            if elapsed >= timeout:
                self.stderr.write(
                    self.style.ERROR(
                        f"Database not available after {timeout} seconds. Aborting."
                    )
                )
                raise SystemExit(1)

            try:
                db_conn = connections["default"]
                db_conn.ensure_connection()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Database available! (took {elapsed:.1f}s)"
                    )
                )
                return
            except OperationalError:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Database unavailable ({elapsed:.1f}s elapsed), "
                        f"retrying in {interval}s..."
                    )
                )
                time.sleep(interval)
