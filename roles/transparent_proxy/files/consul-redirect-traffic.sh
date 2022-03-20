#!/usr/bin/env bash

# This is a small wrapper around `consul connect redirect-traffic` which
# determines the user ID for the `envoy` process prior to executing the command
# to install the redirect rules so that it can be exempted from traffic
# redirection.
#
# Syntax is: consul-redirect-traffic <service name>

# Exit upon receiving any errors
set -o errexit

usage(){
  echo "Usage: $(basename "$0") <service_name>"
  exit 1
}

# Ensure a service name was provided
if [[ $# -eq 0 ]]; then
    usage
fi

SERVICE_NAME=$1

# Obtain the user ID for envoy
PROXY_UID=$(id --user envoy)

SERVICE_CONFIG_DIR="/srv/consul/config/services/${SERVICE_NAME}"

SERVICE_REGISTRATION_FILE="${SERVICE_CONFIG_DIR}/registration.json"
if [[ -f $SERVICE_REGISTRATION_FILE ]]; then
  CONFIGURED_PROXY_MODE=$(jq --raw-output .service.connect.sidecar_service.proxy.mode "${SERVICE_REGISTRATION_FILE}")

  DIRECT_PROXY_MODE="direct"

  # Do not install the redirect rules if the proxy is operating in `direct` mode.
  if [[ "$CONFIGURED_PROXY_MODE" = "${DIRECT_PROXY_MODE}" ]]; then
    exit
  fi
fi

# Include extra redirection exemptions if present
SERVICE_EXTRA_ARGS_FILE="${SERVICE_CONFIG_DIR}/extra-args.json"
if [[ -f "${SERVICE_EXTRA_ARGS_FILE}" ]]; then
  EXTRA_REDIRECT_ARGS=$(jq --raw-output .redirect "${SERVICE_EXTRA_ARGS_FILE}")
fi

eval consul connect redirect-traffic \
    -proxy-id="${SERVICE_NAME}-sidecar-proxy" \
    -proxy-uid="${PROXY_UID}" \
    "${EXTRA_REDIRECT_ARGS}"
