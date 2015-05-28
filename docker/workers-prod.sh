#!/bin/bash
. /evething-env/bin/activate

export C_FORCE_ROOT="yes"
export PYTHONUNBUFFERED=1

cd /evething
# Probaly wont work, we need to start them up in the foreground for docker to manage, maybe a container for each queue?
celery multi start low medium high -A evething -Q:low et_low -c:low 5 -Q:medium et_medium -c:medium 5 -Q:high et_high -c:high 1
