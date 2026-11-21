from django.core.management.base import BaseCommand

from core.students.identity import seed_student_emails


class Command(BaseCommand):
    help = "Bootstrap email reservations once, with every active site online."

    def handle(self, *args, **options):
        self.stdout.write(f"Reserved {seed_student_emails()} student emails; registry ready.")
