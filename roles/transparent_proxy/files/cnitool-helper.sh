#!/usr/bin/env bash

# This is a small wrapper around `cnitool` to help determine the proper network
# to use for a given processs.
#
# Syntax is: cnitool-helper <operation> <service name>

# Exit upon receiving any errors
set -o errexit

usage(){
  echo "Usage: $(basename "$0") <add|del> <service_name>"
  exit 1
}

# Ensure a service name was provided
if [[ $# -ne 2 ]]; then
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

DEFAULT_CONFIG_PATH="/srv/consul/conf/mesh.json"
SERVICE_CONFIG_PATH="/srv/consul/conf/services/${SERVICE_NAME}"
EXTRA_ARGS_PATH="${SERVICE_CONFIG_PATH}/extra-args.json"

# Require default config to be present
if [[ ! -f "${DEFAULT_CONFIG_PATH}" ]]; then
  echo "ERROR: ${DEFAULT_CONFIG_PATH} does not exist"
  exit 1
fi

if [[ (-f "${EXTRA_ARGS_PATH}") ]]; then
  # Attempt to use the network specified in the extra args file
  CNI_NETWORK=$(jq --slurpfile default "${DEFAULT_CONFIG_PATH}" --raw-output '.network // $default.network' "$EXTRA_ARGS_PATH")
else
  # If no extra args file is present, use the network from the default config
  CNI_NETWORK=$(jq --raw-output .network "$DEFAULT_CONFIG_PATH")
fi

# Determine the port assigned by Consul port for this proxy
PROXY_PORT=$(curl --no-progress-meter --stderr - "${CONSUL_HTTP_ADDR}/v1/agent/service/${SERVICE_NAME}-sidecar-proxy" | jq --raw-input 'try (fromjson | .Port) catch error("Unable to retrieve proxy port from Consul")')

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
