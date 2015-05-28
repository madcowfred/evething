#!/bin/bash
. /evething-env/bin/activate

export PYTHONUNBUFFERED=1

cd /evething/
gunicorn evething.wsgi -b 0.0.0.0
