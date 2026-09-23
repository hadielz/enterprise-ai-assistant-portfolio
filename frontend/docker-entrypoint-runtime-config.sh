#!/bin/sh
set -eu
API_BASE_URL_VALUE="${API_BASE_URL:-http://localhost:8000/api}"
printf 'window.__APP_CONFIG__ = { apiBaseUrl: "%s" };\n' "$API_BASE_URL_VALUE" \
  > /usr/share/nginx/html/runtime-config.js
