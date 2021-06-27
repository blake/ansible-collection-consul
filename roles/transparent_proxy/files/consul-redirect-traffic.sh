#!/usr/bin/env bash

# This is a small wrapper around `consul connect redirect-traffic` which
# Determines the user ID for the `consul` process and `envoy` sidecar
# prior to executing the command to install the redirect rules.
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

# Obtain user IDs for consul and envoy
CONSUL_UID=$(id --user consul)
PROXY_UID=$(id --user envoy)

# Redirect DNS traffic to Consul using iptables if systemd version < 246
SYSTEMD_VERSION=$(systemd --version | awk 'NR==1 { print $2 }')

if [[ ${SYSTEMD_VERSION} -lt 246 ]]; then
    iptables --table nat --append OUTPUT --destination localhost --proto udp --match udp --dport 53 --jump REDIRECT --to-ports 8600
    iptables --table nat --append OUTPUT --destination localhost --proto tcp --match tcp --dport 53 --jump REDIRECT --to-ports 8600
fi

if [[ -f "/etc/consul.d/service-registration.json" ]]; then
  CONFIGURED_PROXY_MODE=$(jq --raw-output .service.connect.sidecar_service.proxy.mode /etc/consul.d/service-registration.json)

  DIRECT_PROXY_MODE="direct"

  # Do not install the redirect rules if the proxy is operating in `direct` mode.
  if [[ "$CONFIGURED_PROXY_MODE" = "${DIRECT_PROXY_MODE}" ]]; then
    exit
  fi
fi

# Include extra redirection exemptions if present
if [[ -f "/srv/consul/extra-args.json" ]]; then
  EXTRA_REDIRECT_ARGS=$(jq --raw-output .redirect /srv/consul/extra-args.json)
fi

eval consul connect redirect-traffic \
    -proxy-id="${1}-sidecar-proxy" \
    -proxy-uid="${PROXY_UID}" \
    -exclude-uid="${CONSUL_UID}" \
    "${EXTRA_REDIRECT_ARGS}"
