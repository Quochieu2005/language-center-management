#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if sys.argv[1:2] == ["runserver"]:
        # Keep Django's local development server off the default port 8000.
        value_options = {"--settings", "--pythonpath", "--verbosity"}
        has_address = False
        skip_value = False
        for argument in sys.argv[2:]:
            if skip_value:
                skip_value = False
                continue
            if argument in value_options:
                skip_value = True
                continue
            if not argument.startswith("-"):
                has_address = True
                break
        if not has_address:
            sys.argv.insert(2, "127.0.0.1:8001")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Không tải được Django. Hãy kích hoạt môi trường .venv và cài requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
