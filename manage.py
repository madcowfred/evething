#!/usr/bin/env python

import os
import sys

# Enforce Django 1.5
from django import get_version
if get_version() < '1.6':
    print
    print 'ERROR: EVEthing requires Django version 1.5 or above!'
    print
    sys.exit(1)

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
