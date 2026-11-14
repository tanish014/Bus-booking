#!/usr/bin/env bash
# makes a self signed certificate for local HTTPS (browser will show a warning, that is normal)
set -e
export MSYS_NO_PATHCONV=1
mkdir -p nginx/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout nginx/certs/server.key -out nginx/certs/server.crt \
  -subj "/C=IN/O=BusBookingDemo/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
echo "certificate created in nginx/certs/"
