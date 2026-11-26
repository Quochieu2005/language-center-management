"""Replay queued Blog writes to sites that were offline; --once runs a single pass."""

import time

from django.core.management.base import BaseCommand
from django.db import DatabaseError, close_old_connections

from core.blog.services import PublicBlogUnavailable
from core.blog.sync_queue import reconcile_pending_blog_writes


class Command(BaseCommand):
    help = "Reconcile pending Blog writes; --once runs one pass."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        last_state = None
        last_error = None
        while True:
            close_old_connections()
            try:
                result = reconcile_pending_blog_writes()
                state = (result["pending_count"], result["review_count"])
                if options["once"] or state != last_state:
                    self.stdout.write(str(result))
                last_state = state
                last_error = None
            except (DatabaseError, PublicBlogUnavailable) as exc:
                if options["once"]:
                    raise
                error = type(exc).__name__
                if error != last_error:
                    self.stderr.write(error)
                last_error = error
            if options["once"]:
                return
            time.sleep(5)
