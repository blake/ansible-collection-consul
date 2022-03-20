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

case $1 in
  add | del | check)
    operation="$1"
    ;;

  *)
    echo "Invalid operation: $1"
    exit 1
    ;;
esac

CONSUL_HTTP_ADDR="http://localhost:8500"
SERVICE_NAME="$2"

SERVICE_CONFIG_PATH="/srv/consul/config/services/${SERVICE_NAME}"
EXTRA_ARGS_PATH="${SERVICE_CONFIG_PATH}/extra_args.json"

if [[ -f "${EXTRA_ARGS_PATH}" ]]; then
  CNI_NETWORK=$(jq --raw-output .network "$EXTRA_ARGS_PATH")
else
  # Use default network of `envoynetwork`
  CNI_NETWORK="envoynetwork"
fi

# Determine the port assigned by Consul port for this proxy
PROXY_PORT=$(curl --silent "${CONSUL_HTTP_ADDR}/v1/agent/service/${SERVICE_NAME}-sidecar-proxy" | jq .Port)

# Generate the CAP_ARGS for the portmap CNI plugin so that it forwards the
# correct host port to this proxy
port_mapping_args=$(jq --compact-output --null-input --arg port "$PROXY_PORT" '{portMappings: [{hostPort: $port|tonumber, containerPort: $port|tonumber, protocol: "tcp"}]}')

if [[ "$operation" = "del" ]]; then
  if ! systemctl is-active "systemd-netns@${SERVICE_NAME}.service"; then
    # The namespace does not exist, which will cause the `del` operation to fail
    # and prevent cleanup of any remaining CNI objects.
    #
    # Start the namespace in the background to allow cleanup to continue.
    # The namespace should be cleaned up by the remaining scripts that manage
    # the namespace.
    systemctl start "systemd-netns@${SERVICE_NAME}.service"
  fi
fi

export CNI_PATH=/opt/cni/bin
CAP_ARGS=$port_mapping_args \
  cnitool \
  "$operation" \
  $CNI_NETWORK \
  "/var/run/netns/${SERVICE_NAME}"
