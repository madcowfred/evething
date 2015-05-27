#!/bin/bash
. /evething-env/bin/activate

export PYTHONUNBUFFERED=1

/evething/manage.py runserver 0.0.0.0:8000
