#!/usr/bin/env bash

# This is a small wrapper around `consul connect redirect-traffic` which
# determines the user ID for the `envoy` process prior to executing the command
# to install the redirect rules so that it can be exempted from traffic
# redirection.
#
# Syntax is: consul-redirect-traffic <service name>

# Exit upon receiving any errors
set -o errexit

SCRIPT_NAME=$(basename "$0")

usage(){
  echo "Usage: $SCRIPT_NAME <service_name>"
  exit 1
}

LONG=proxy-inbound-port:
SHORT=p:
OPTS=$(getopt --alternative --name "$SCRIPT_NAME" --options $SHORT --longoptions $LONG -- "$@")

# Obtain the user ID for envoy
PROXY_UID=$(id --user envoy)

eval set -- "$OPTS"

while :
do
  case "$1" in
    -p | --proxy-inbound-port )
      PROXY_INBOUND_PORT="$2"
      shift 2
      ;;
    --)
      shift;
      break
      ;;
    *)
      echo "Unexpected option: $1"
      help
      ;;
  esac
done

# Only allow a service name to be present, or the proxy-inbound-port flag provided
if [[ $# -eq 1 ]]; then
  SERVICE_NAME="${1}"

  # If proxy-inbound-port is set
  if [[ -n $PROXY_INBOUND_PORT ]]; then
    usage
  fi
elif [[ $# -eq 0 ]]; then
  # If proxy-inbound-port is not set
  if [[ -z "$PROXY_INBOUND_PORT" ]]; then
    usage
  fi
elif [[ $# -gt 1 ]]; then
  usage
fi

if [[ -n "${SERVICE_NAME}" ]]; then
  SERVICE_CONFIG_DIR="/srv/consul/conf/services/${SERVICE_NAME}"
  SERVICE_REGISTRATION_FILE="${SERVICE_CONFIG_DIR}/registration.json"
  if [[ -f $SERVICE_REGISTRATION_FILE ]]; then
    CONFIGURED_PROXY_MODE=$(jq --raw-output .service.connect.sidecar_service.proxy.mode "${SERVICE_REGISTRATION_FILE}")

    DIRECT_PROXY_MODE="direct"

    # Do not install the redirect rules if the proxy is operating in `direct` mode.
    if [[ "$CONFIGURED_PROXY_MODE" = "${DIRECT_PROXY_MODE}" ]]; then
      exit
    fi
  fi

  # Require default config to be present
  DEFAULT_CONFIG_PATH="/srv/consul/conf/mesh.json"
  if [[ ! -f "${DEFAULT_CONFIG_PATH}" ]]; then
    echo "ERROR: ${DEFAULT_CONFIG_PATH} does not exist"
    exit 1
  fi

  CONSUL_DNS_IP=$(jq --raw-output '.dns_ip // halt_error' "$DEFAULT_CONFIG_PATH")

  # Include extra redirection exemptions if present
  SERVICE_EXTRA_ARGS_FILE="${SERVICE_CONFIG_DIR}/extra-args.json"
  if [[ -f "${SERVICE_EXTRA_ARGS_FILE}" ]]; then
    EXTRA_REDIRECT_ARGS=$(jq --raw-output .redirect "${SERVICE_EXTRA_ARGS_FILE}")
  fi
fi

if [[ -n "${SERVICE_NAME}" ]]; then

  eval consul connect redirect-traffic \
      -proxy-id="${SERVICE_NAME}-sidecar-proxy" \
      -proxy-uid="${PROXY_UID}" \
      -consul-dns-ip="${CONSUL_DNS_IP}" \
      "${EXTRA_REDIRECT_ARGS}"
else
  # Command for Nomad traffic redirection
  eval consul connect redirect-traffic \
      -proxy-uid="${PROXY_UID}" \
      -proxy-inbound-port="${PROXY_INBOUND_PORT}" \
      -consul-dns-ip="172.17.0.1"
fi
