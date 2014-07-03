#!/bin/bash
# Start EVEthing services and perform firstboot initialization
cd /evething

if [ ! -f "/evething/data/.initialized" ]; then
    echo "Performing first-run initialization"
    mkdir -p /evething/data/postgresql
    chown postgres /evething/data/postgresql
    chmod 0700 /evething/data/postgresql
    sudo -u postgres /usr/lib/postgresql/9.3/bin/initdb /evething/data/postgresql/

    service postgresql start
    sudo -u postgres createuser -d evething
    sudo -u evething createdb evething
    
    curl https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2 \
        | bunzip2 > /sqlite-latest.sqlite

    mkdir -p /evething/data/static
    chown evething /evething/data/static
    sudo -u evething python manage.py syncdb --noinput
    sudo -u evething python manage.py collectstatic --noinput
    sudo -u evething python manage.py migrate --all
    sudo -u evething python import.py

    echo
    echo
    echo "Now you will be asked to create an initial user:"
    echo

    sudo -u evething python manage.py createsuperuser --email=${admin_email}

    rm /sqlite-latest.sqlite
    service postgresql stop

    echo 1 > /evething/data/.initialized
fi

# Start our services
service postgresql start
service memcached start
/etc/init.d/redis-server start
sudo -u evething celery worker -A evething -B -Q et_high,et_medium,et_low -c 2 --detach

echo
echo "EVEthing will now be started."

# Get this party started
sudo -u evething python /evething/manage.py runfcgi host=0.0.0.0 port=8081 \
    pidfile=/evething/evething-fcgi.pid
nginx
service postgresql stop
