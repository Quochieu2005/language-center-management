"""Run beside the API; unfinished deliveries survive worker or database restarts."""

import time

from django.core.management.base import BaseCommand
from django.db import DatabaseError, close_old_connections

from core.auth.account_replication import queue_account_reconciliation, sync_accounts
from core.auth.service_common import AuthInfrastructureUnavailable
from core.auth.password_reset import _resume_pending_password_resets


class Command(BaseCommand):
    help = "Deliver pending account replicas; --once runs one batch."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        next_reconciliation = 0
        while True:
            close_old_connections()
            try:
                _resume_pending_password_resets()
                if time.monotonic() >= next_reconciliation:
                    queue_account_reconciliation()
                    next_reconciliation = time.monotonic() + 60
                result = sync_accounts()
                if options["once"] or result["delivered"] or result["deferred"]:
                    self.stdout.write(str(result))
            except (DatabaseError, AuthInfrastructureUnavailable) as exc:
                if options["once"]:
                    raise
                self.stderr.write(type(exc).__name__)
            if options["once"]:
                return
            time.sleep(5)
