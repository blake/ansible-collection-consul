#!/usr/bin/env python3
# Copyright 2022 Blake Covarrubias
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
This script sets up the necessary dependencies to run a named service in Consul
service mesh using transparent proxy.
"""

import argparse
import json
import sys
import os.path
from pathlib import Path

sys.path.insert(1, "./roles/transaprent_proxy/files")
from generate_sidecar_configs import ServiceConfigParameters

#     # Sanitize values to ensure that they don't have trailing whitespace
#     @staticmethod
#     def parse_csv(value: str):
#         """Parses a list of comma-separated values into a dict"""
#         values = value.split(sep=",")
#         sanitized_values: map[str] = map(lambda v: v.strip(), values)

#         return list(sanitized_values)

#     @staticmethod
#     def parse_upstream_declaration(value: str):
#         """Attempts to parse a string into a valid upstream definition."""
#         parts = value.split(sep=":")

#         upstream_definition = UpstreamDefinition()

#         # TODO (blake): Log error
#         # Invalid upstream declaration. Too many components.
#         if len(parts) > 3:
#             return upstream_definition

#         # Initialize all three variables as the same type
#         datacenter = destination_name = port = ""

#         if parts[0] == "prepared_query":
#             destination_type, destination_name, port = parts
#             upstream_definition["destination_type"] = destination_type
#         else:
#             destination_type = "service"
#             destination_name, *remainder = parts
#             if len(remainder) == 1:
#                 port = int(remainder[0])
#             elif len(remainder) == 2:
#                 port, datacenter = remainder

#         upstream_definition["local_bind_port"] = int(port)

#         if datacenter:
#             upstream_definition["datacenter"] = datacenter

#         # If there's a period in the destination name, this is a namespaced
#         # service
#         if "." in destination_name:
#             service, namespace = destination_name.split(sep=".")
#             upstream_definition.update(
#                 {"destination_name": service, "destination_namespace": namespace}
#             )
#         else:
#             upstream_definition["destination_name"] = destination_name

#         return upstream_definition

#     def service_name(self) -> Union[str, None]:
#         """Return the service name declared in the service configuration."""
#         service_definition = self.service_config["service"]
#         name = service_definition.get("name")
#         return name

#     def __init__(self, config: str):
#         # Extra arguments to pass to 'consul connect envoy'
#         self.connect_envoy_args: List[str] = []

#         # Extra arguments to pass to 'consul connect redirect-traffic'
#         self.connect_redirect_traffic_args: List[str] = []

#         # Extra arguments to pass to `envoy`
#         self.extra_envoy_args = ""

#         # Read the service configuration file
#         self.json_config = self.read_json_file(json_file=config)
#         self.service_config = self.parse_service_config()

#     def parse_proxy_config(self, proxy_config: str):
#         """
#         Parse the proxy provided on the CLI.
#         """

#         proxy_params = self.service_config["service"]["connect"]["sidecar_service"][
#             "proxy"
#         ]

#         proxy_config_params = {}

#         proxy_config_vars: List[str] = self.parse_csv(proxy_config)
#         for config in proxy_config_vars:
#             key, value = config.split(sep="=")
#             proxy_config_params[key] = value

#         if "config" in proxy_params:
#             proxy_params["config"].update(proxy_config_params)
#         else:
#             proxy_params["config"] = proxy_config_params

#         return proxy_params

#     def parse_service_config(self):
#         """
#         Parses the provided service configuration file and returns a dictionary
#         representation of a Consul service registration for the named service.
#         """

#         # Prefix for each Connect annotation
#         annotation_prefix = "consul.hashicorp.com/"
#         alpha_annotation_prefix = f"alpha.{annotation_prefix}"

#         connect_definition = ConnectDefinition(sidecar_service={})
#         service_definition = ServiceDefinition(connect=connect_definition)
#         proxy_config = ProxyConfig()

#         if "annotations" not in self.json_config:
#             sys.exit("Service configuration is missing annotations.")

#         traffic_exclusion_options = frozenset(
#             (
#                 "transparent-proxy-exclude-inbound-ports",
#                 "transparent-proxy-exclude-outbound-cidrs",
#                 "transparent-proxy-exclude-outbound-ports",
#                 "transparent-proxy-exclude-uids",
#             )
#         )

#         # Initialize tagged virtual address variable. Used later to added
#         # tagged address if proxy.mode is 'transparent'
#         tagged_virtual_address = ""

#         annotations: Dict[str, str] = self.json_config["annotations"]
#         service_metadata: Dict[str, str] = {}

#         for annotation, value in annotations.items():
#             # Handle alpha annotations differently
#             if annotation.startswith(alpha_annotation_prefix):
#                 option = self.removeprefix(annotation, alpha_annotation_prefix)

#                 if option == "virtual-ip":
#                     tagged_virtual_address = value

#                 continue

#             if not annotation.startswith(annotation_prefix):
#                 continue

#             option = self.removeprefix(annotation, annotation_prefix)

#             # Set transparent proxy config in service registration
#             if option == "connect-service":
#                 service_definition["name"] = value
#             elif option == "connect-service-port":
#                 service_definition["port"] = int(value)
#             elif option == "connect-service-upstreams":
#                 specified_upstreams = self.parse_csv(value)

#                 # Parsed upstream definitions
#                 upstreams: List[UpstreamDefinition] = []

#                 for upstream in specified_upstreams:
#                     upstream_declaration = self.parse_upstream_declaration(upstream)
#                     # Ensure that returned value is not empty
#                     if upstream_declaration:
#                         upstreams.append(upstream_declaration)

#                 proxy_config["upstreams"] = upstreams

#             elif option == "envoy-extra-args":
#                 self.extra_envoy_args = value
#             elif option == "service-tags":
#                 service_definition["tags"] = self.parse_csv(value)
#             elif option in traffic_exclusion_options:
#                 flag = self.removeprefix(option, "transparent-proxy-")
#                 # Remove trailing, plural 's' on flag
#                 flag = flag.rstrip("s")

#                 # Ensure value is a string
#                 value = str(value)
#                 exempt_values = self.parse_csv(value)
#                 for exemption in exempt_values:
#                     self.add_redirect_traffic_arg(flag, exemption)
#             elif option == "prometheus-scrape-path":
#                 self.add_connect_envoy_arg(option, value)
#             elif option == "transparent-proxy":
#                 proxy_config["mode"] = "transparent" if bool(value) else "direct"
#             elif option.startswith("service-meta-"):
#                 meta_key = self.removeprefix(option, "service-meta-")
#                 service_metadata[meta_key] = value

#         # If service metadata exists, append it to service definition
#         if service_metadata:
#             service_definition["meta"] = service_metadata

#         # If custom proxy parameters are configured, add them to the service
#         # definition
#         if proxy_config:
#             connect_definition["sidecar_service"]["proxy"] = proxy_config

#         # Append port to 'virtual' tagged address
#         if tagged_virtual_address and proxy_config.get("mode") == "transparent":
#             service_port = service_definition.get("port")
#             if service_port:
#                 tagged_address = TaggedAddress(
#                     address=tagged_virtual_address, port=service_port
#                 )
#                 connect_definition["sidecar_service"][
#                     "tagged_addresses"
#                 ] = TaggedAddresses(virtual=tagged_address)

#         self.service_registration = dict(service=service_definition)
#         return self.service_registration

#     def generate_connect_redirect_args(self):
#         """Generate optional arguments to pass to `consul connect redirect-traffic`."""
#         return " ".join(self.connect_redirect_traffic_args)

#     def generate_connect_envoy_args(self):
#         """Generate optional arguments to pass to `consul connect envoy`."""
#         return " ".join(self.connect_envoy_args)

#     def generate_envoy_args(self):
#         """
#         Generate optional arguments to pass directly to the Envoy processes
#         spawned by `consul connect envoy`.
#         """
#         return self.extra_envoy_args

#     def generate_service_config(self):
#         """Return the service registration as a JSON string."""
#         return json.dumps(self.service_config, indent=2, sort_keys=True)

#     def read_json_file(self, json_file: str):
#         """Attempt to parse the provided file as a JSON object."""
#         try:
#             with open(file=json_file) as file_handle:
#                 service_configuration = json.load(fp=file_handle)
#         except:
#             sys.exit("Unable to parse JSON registration.")

#         return service_configuration


# def start_systemd_process(name: str):
#     """Start the named process using systemd."""
#     if sys.platform != "linux":
#         return

#     import dbus

#     sysbus = dbus.SystemBus()
#     systemd1 = sysbus.get_object(
#         bus_name="org.freedesktop.systemd1", object_path="/org/freedesktop/systemd1"
#     )
#     manager = dbus.Interface(
#         object=systemd1, dbus_interface="org.freedesktop.systemd1.Manager"
#     )

#     # See https://wiki.freedesktop.org/www/Software/systemd/dbus/ for information
#     # on each function
#     manager.EnableUnitFiles([f"{name}.service"], False, True)
#     manager.StartUnit(f"{name}.service", "fail")


def link_dns_dir(name: str, network: str, dns_dir: str):
    """Link the DNS directory for the given service to the target network name."""
    netns_path = Path("/etc/netns")

    # Create /etc/netns directory if it doesn't exist
    if not netns_path.exists():
        netns_path.mkdir()
    elif netns_path.exists() and not netns_path.is_dir():
        raise Exception(f"{netns_path} is not a directory")

    # The DNS path for the provided network is '/srv/consul/conf/dns/<network>'
    netns_dns_path = Path(dns_dir).joinpath(network)

    if not netns_dns_path.exists():
        raise Exception(
            f"{netns_dns_path} does not exist. Unable to link DNS config for network."
        )

    # The path for the given service is '/etc/netns/<name>'
    service_netns_path = netns_path.joinpath(name)

    # Check if the service's netns is a symlink.
    # Symlinks should be checked first because `.exists()` calls with fail if
    # if the symlink points to a non-existent path.
    if service_netns_path.is_symlink():
        # If the symlink exists, and is pointing to the correct path, we're done
        if service_netns_path.exists() and service_netns_path.resolve() == netns_path:
            return
        # Symlink exists, but is pointing to the wrong path. Remove it
        elif service_netns_path.exists() and service_netns_path.resolve() != netns_path:
            service_netns_path.unlink()
    # The service's netns is not a symlink
    elif service_netns_path.exists():
        # If it is a directory, remove it
        if service_netns_path.is_dir():
            service_netns_path.rmdir()
        # If it is a file, remove it
        elif service_netns_path.is_file():
            # Remove file
            service_netns_path.unlink()

    # Symlink path to the DNS config for this service
    service_netns_path.symlink_to(netns_dns_path)


def main():
    """Main entry point."""
    basedir = Path(os.path.realpath(__file__)).parent
    service_registration_file = "registration.json"

    extra_arguments_filename = "extra-args.json"

    supported_outputs = ["connect-envoy", "envoy", "redirect", "service-registration"]

    parser = argparse.ArgumentParser(
        description="Register a service with Consul and start an Envoy process."
    )
    parser.add_argument("-f", "--filename", required=True)
    parser.add_argument("--network", default="envoynetwork")
    args = parser.parse_args()

    if not Path(args.filename).exists():
        sys.exit(
            f"{args.filename} does not exist. Cannot generate service registration."
        )

    # Parses service registration file
    service_config = ServiceConfigParameters(config=args.filename)

    type_func_map = {
        "connect-envoy": service_config.generate_connect_envoy_args,
        "envoy": service_config.generate_envoy_args,
        "redirect": service_config.generate_connect_redirect_args,
        "service-registration": service_config.generate_service_config,
    }

    # Write the generated configurations to files
    service_config_dir = basedir.joinpath("config/services").joinpath(service_config.service_name())

    extra_args = {}
    for key, func_to_exec in type_func_map.items():
        result = func_to_exec()

        if key == "service-registration":
            with open(
                service_config_dir.joinpath(service_registration_file), mode="w+"
            ) as file_handle:
                file_handle.write(result)
        else:
            extra_args[key] = result

    # Add CNI network to extra-args.json
    extra_args["network"] = args.network

    # Write output of extra arguments to disk
    if extra_args:
        with open(service_config_dir.joinpath(extra_arguments_filename), mode="w+") as file_handle:
            json.dump(extra_args, fp=file_handle, indent=2)

    # Link the service's namespace to the correct DNS configuration for the
    # configured network
    try:
        link_dns_dir(name=service_config.service_name(), network=args.network, dns_dir="/srv/consul/conf/dns")
    except Exception as e:
        raise e


    # TODO: (blake) Generate token for service if ACLs are enabled, register service,
    # create files for other scripts to know the network to use, create a token


    # # Print the requested resource to stdout if running in dry mode
    # if args.dry:
    #     if not args.type:
    #         parser.error("--dry requires --type to be specified.")

    #     func_to_exec = type_func_map[args.type]
    #     result = func_to_exec()

    #     if result:
    #         print(result)
    #     sys.exit()

    # # Write the generated configurations to files
    # extra_args = {}
    # for key, func_to_exec in type_func_map.items():
    #     result = func_to_exec()

    #     if key == "service-registration":
    #         with open(service_registration_file, mode="w+") as file_handle:
    #             file_handle.write(result)
    #     else:
    #         extra_args[key] = result

    # # Write output of extra arguments to disk
    # if extra_args:
    #     with open(extra_arguments_filename, mode="w+") as file_handle:
    #         json.dump(extra_args, fp=file_handle, indent=2)

    # # Lastly, try to start the systemd unit for the configured service
    # service_name = service_config.service_name()
    # if service_name:
    #     start_systemd_process(name=service_name)


if __name__ == "__main__":
    main()
