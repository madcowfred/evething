# Pull base image.
FROM ubuntu:14.04

MAINTAINER Eric Gillingham "Gillingham@bikezen.net"

# Setup unprivileged user
RUN adduser --disabled-password --gecos '' evething

COPY . /evething
RUN chown -R evething:evething /evething
VOLUME /evething

CMD ["/bin/true"]