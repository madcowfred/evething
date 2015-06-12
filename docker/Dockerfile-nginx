# Pull base image.
FROM nginx

MAINTAINER Eric Gillingham "Gillingham@bikezen.net"

# Copy custom configuration file from the current directory
COPY docker/nginx.conf /etc/nginx/nginx.conf

CMD ["nginx"]