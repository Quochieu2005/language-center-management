"""Retry durable KhoaHoc catalog writes while the API worker is running."""

import time

from django.core.management.base import BaseCommand
from django.db import DatabaseError, close_old_connections

from core.catalog.course_services import reconcile_pending_course_writes
from core.catalog.services import SharedCatalogUnavailable


class Command(BaseCommand):
    help = "Reconcile pending shared-course writes; --once runs one pass."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        last_state = None
        last_error = None
        while True:
            close_old_connections()
            try:
                result = reconcile_pending_course_writes()
                state = (result["pending_count"], tuple(result["pending_sites"]))
                if options["once"] or state != last_state:
                    self.stdout.write(str({"pending_count": state[0], "pending_sites": state[1]}))
                last_state = state
                last_error = None
            except (DatabaseError, SharedCatalogUnavailable) as exc:
                if options["once"]:
                    raise
                error = type(exc).__name__
                if error != last_error:
                    self.stderr.write(error)
                last_error = error
            if options["once"]:
                return
            time.sleep(5)
