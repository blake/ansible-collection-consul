#!/usr/bin/env bash

# This is a small wrapper around `cnitool` to help determine the proper network
# to use for a given processs.
#
# Syntax is: cnitool-helper <operation> <service name>

# Exit upon receiving any errors
set -o errexit

set -x

usage(){
  echo "Usage: $(basename "$0") <add|del> <service_name>"
  exit 1
}

# Ensure a service name was provided
if [[ $# -eq 0 ]]; then
    usage
fi

# if [[ -f "/srv/consul/services/${1}/config.json" ]]; then
#   CONFIGURED_PROXY_MODE=$(jq --raw-output .service.connect.sidecar_service.proxy.mode /etc/consul.d/service-registration.json)

#   DIRECT_PROXY_MODE="direct"

#   # Do not install the redirect rules if the proxy is operating in `direct` mode.
#   if [[ "$CONFIGURED_PROXY_MODE" = "${DIRECT_PROXY_MODE}" ]]; then
#     exit
#   fi
# fi

export CNI_PATH=/opt/cni/bin
CONSUL_HTTP_ADDR="http://localhost:8500"
CNI_NETWORK="envoynetwork"

case $1 in
  add | del | check)
    operation="$1"
    ;;

  *)
    echo "Invalid operation: $1"
    exit 1
    ;;
esac

PROXY_PORT=$(curl --silent "${CONSUL_HTTP_ADDR}/v1/agent/service/${2}-sidecar-proxy" | jq .Port)
port_mapping_args=$(jq --compact-output --null-input --arg port "$PROXY_PORT" '{portMappings: [{hostPort: $port|tonumber, containerPort: $port|tonumber, protocol: "tcp"}]}')

CAP_ARGS=$port_mapping_args \
  cnitool \
  "$operation" \
  $CNI_NETWORK \
  "/var/run/netns/${2}"
