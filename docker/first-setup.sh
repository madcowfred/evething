#!/bin/bash
. /evething-env/bin/activate
cd /evething/
/evething/manage.py syncdb --noinput
/evething/manage.py migrate --all
/evething/import.py
/evething/manage.py createsuperuser
