from django.core.management.base import BaseCommand

from core.students.identity import seed_student_emails


class Command(BaseCommand):
    help = "Bootstrap email reservations once, with every active site online."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-missing-sites", action="store_true",
            help="Skip unreachable sites (never the authority). An email held only by a skipped site can then be "
                 "registered again; re-check those sites once they are back.",
        )

    def handle(self, *args, **options):
        reserved, skipped = seed_student_emails(allow_missing_sites=options["allow_missing_sites"])
        self.stdout.write(f"Reserved {reserved} student emails; registry ready.")
        if skipped:
            self.stdout.write(self.style.WARNING(f"Skipped unreachable sites: {', '.join(skipped)}. Emails held only there are not reserved."))
