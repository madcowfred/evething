#!/bin/bash
. /evething-env/bin/activate

export C_FORCE_ROOT="yes"
export PYTHONUNBUFFERED=1

celery worker -A evething -B -Q et_high,et_medium,et_low -c 2
