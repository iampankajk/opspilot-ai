#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p .certs
if [ -e .certs/localhost-key.pem ] || [ -e .certs/localhost.pem ]; then
  echo 'A development certificate/key already exists; leaving both untouched.'
  exit 1
fi
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout .certs/localhost-key.pem -out .certs/localhost.pem \
  -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
echo 'Created a local-only certificate. No system trust settings were changed.'
