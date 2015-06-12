# Pull base image.
FROM ubuntu:14.04

MAINTAINER Eric Gillingham "Gillingham@bikezen.net"

# Setup unprivileged user
RUN adduser --disabled-password --gecos '' evething && \
    mkdir /evething-env && \
    mkdir /evething && \
    chown evething /evething-env && \
    chown evething /evething

# Install.
RUN apt-get update && \
    apt-get install -y python2.7 python2.7-dev python-virtualenv python-pip \
                    libpq-dev \
                    build-essential wget

USER evething
WORKDIR /evething

COPY requirements.txt /evething/
COPY docker/requirements-docker.txt docker/requirements-docker-prod.txt /evething/docker/

VOLUME /evething

# Install python deps into virtualenv, and activate at login
RUN /usr/bin/virtualenv /evething-env && \
    . /evething-env/bin/activate && \
    pip install -r requirements.txt -r docker/requirements-docker.txt -r docker/requirements-docker-prod.txt && \
    echo '. /evething-env/bin/activate' >> $HOME/.bashrc

# Define default command, this gets overwritten by docker-compose
CMD ["/evething/docker/gunicorn.sh"]
