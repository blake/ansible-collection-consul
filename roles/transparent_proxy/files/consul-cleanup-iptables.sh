#!/usr/bin/env bash

# This is a small helper script to clean up iptables rules installed by
# Consul when the proxy stops or restarts.
#
# Syntax is: consul-cleanup-iptables

# Exit upon receiving any errors
set -o errexit

# Remove rules from NAT table
iptables --table nat --flush

# Delete empty chains
declare -a consul_chains=("INBOUND" "IN_REDIRECT" "OUTPUT" "REDIRECT")

for i in "${consul_chains[@]}"
do
  iptables --table nat --delete-chain "CONSUL_PROXY_${i}"
done
