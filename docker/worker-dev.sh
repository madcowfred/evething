#!/bin/bash
. /evething-env/bin/activate

export PYTHONUNBUFFERED=1

celery worker -A evething -B -Q et_high,et_medium,et_low -c 2
