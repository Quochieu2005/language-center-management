"""Site-local slug allocation for student profiles."""

from core.slug_utils import make_slug


def available_student_slug(cursor, name: str, custom_slug: str | None = None) -> str:
    base = make_slug(name, custom_slug, max_length=160)
    suffix = 1
    while True:
        candidate = base if suffix == 1 else f"{base[:159 - len(str(suffix))].rstrip('-')}-{suffix}"
        cursor.execute(
            "SELECT TOP (1) 1 FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) WHERE slug = %s",
            [candidate],
        )
        if cursor.fetchone() is None:
            return candidate
        suffix += 1
