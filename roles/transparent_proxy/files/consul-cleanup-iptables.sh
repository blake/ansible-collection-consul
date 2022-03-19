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

# Remove the CONSUL_DNS_REDIRECT chain that is created by Consul 1.11.x
# (Ignore exit code so that this continues to run on older Consul versions)
iptables --table nat --delete-chain "CONSUL_DNS_REDIRECT" || true

# If there are no other chains in the NAT table being managed by other programs,
# all user-defined chains can be removed with the following command, in place of
# the above `--delete-chain` lines.

# iptables --table nat --delete-chain
