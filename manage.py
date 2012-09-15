#!/usr/bin/env python

import os
import sys

# try using cdecimal for faster Decimal type
try:
    import cdecimal
except ImportError:
    pass
else:
    sys.modules["decimal"] = cdecimal

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evething.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
