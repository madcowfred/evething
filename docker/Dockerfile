# A Dockerfile for EVEthing
# (https://github.com/madcowfred/evething/tree/develop) running on PostgreSQL
# and a single worker group
FROM ubuntu

MAINTAINER Rob Haswell <rob@clusterhq.com>

# We need a system user otherwise everything complains about being root.
RUN adduser --system --ingroup adm evething

RUN apt-get -qq update
RUN apt-get install -qqy \
    celeryd \
    curl \
    git \
    memcached \
    postgresql-9.3 \
    python-celery \
    python-dev \
    python-flup \
    python-memcache \
    python-pip \
    python-psycopg2 \
    python-redis \
    python-sqlite \
    nginx \
    redis-server \
    supervisor

# Download EVEThing
RUN git clone -b develop git://github.com/madcowfred/evething.git
RUN sudo chown -R evething /evething /var/log/celery

# Virtualenv is hard in Dockerfiles so we just install right into the image
RUN pip install -r evething/requirements.txt
RUN pip install django-celery

RUN mkdir /var/lib/evething
RUN chown evething /var/lib/evething

# Add some configuration files
ADD postgresql.conf /etc/postgresql/9.3/main/postgresql.conf
ADD local_settings.py /evething/evething/local_settings.py
ADD nginx_evething.conf /etc/nginx/sites-enabled/evething.conf
ADD supervisor_evething.conf /etc/supervisor/conf.d/evething.conf
ADD firstrun /sbin/firstrun
RUN chmod +x /sbin/firstrun

VOLUME /evething/data
CMD /sbin/firstrun
