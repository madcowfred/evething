Docker build system
===================

This `Dockerfile` builds a single Docker image which can be deployed that provides the whole EVEthing instance, and its dependencies.

The deployment method is an nginx_ server backed onto DJango's wsgi implementation.
A Postgresql_ database is set up and primed with static data on the container's first run.
A Redis_ server acts as the Celery_ broker.

This build is **interactive** on first boot and requires the administrator to supply root credentials.


Building
--------

:

    $ cd docker
    $ docker build -t yourname/evething .


Deployment
----------

This image takes two required environment variables, `admin_name` and `admin_email`.

Additionally a volume is required at `/evething/data`.
This acts as storage for the Postgresql_ server and static caches.

The web server port exposed is `8080`.

A typical invocation would look like::

    $ docker run -i -t \
        -v '/opt/evething-data:/evething/data' -p 80:8080 \
        -e admin_name='Your Name' -e admin_email='admin@example.org' \
        yourname/evething
