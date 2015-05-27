#!/bin/bash
. /evething-env/bin/activate
cd /evething/
npm install
npm install npm-check-updates
/evething/manage.py migrate --noinput
/evething/import.py
/evething/manage.py createsuperuser
