#!/usr/bin/env python3

import argparse
import json
import os.path
import sys
from typing import Dict, List, TypedDict, Union


class UpstreamDefinition(TypedDict, total=False):
    datacenter: str
    destination_name: str
    destination_namespace: str
    destination_type: str
    local_bind_port: int


class ProxyConfig(TypedDict, total=False):
    mode: str
    upstreams: List[UpstreamDefinition]


class ConnectDefinition(TypedDict):
    sidecar_service: Dict[str, ProxyConfig]


class ServiceDefinition(TypedDict, total=False):
    name: str
    connect: ConnectDefinition
    meta: Dict[str, str]
    port: int
    tags: List[str]


class ServiceConfigParameters:

    # Add an argument to the list of args passed to 'consul connect redirect-traffic'
    def add_redirect_traffic_arg(self, option: str, value: str):
        self.connect_redirect_traffic_args.append(f"-{option}={value}")

    # Add an argument to the list of args passed to 'consul connect envoy'
    def add_connect_envoy_arg(self, option: str, value: str):
        self.connect_envoy_args.append(f"-{option}={value}")

    @staticmethod
    def removeprefix(text: str, prefix: str):
        if text.startswith(prefix):
            return text[len(prefix) :]
        return text

    # Sanitize values to ensure that they don't have trailing whitespace
    @staticmethod
    def parse_csv(value: str):
        values = value.split(sep=",")
        sanitized_values = map(lambda v: v.strip(), values)  # type: map[str]

        return list(sanitized_values)

    @staticmethod
    def parse_upstream_declaration(value: str):
        parts = value.split(sep=":")

        upstream_definition = UpstreamDefinition()

        # TODO (blake): Log error
        # Invalid upstream declaration. Too many components.
        if len(parts) > 3:
            return upstream_definition

        # Initialize all three variables as the same type
        datacenter = destination_name = port = ""

        if parts[0] == "prepared_query":
            destination_type, destination_name, port = parts
            upstream_definition["destination_type"] = destination_type
        else:
            destination_type = "service"
            destination_name, *remainder = parts
            if len(remainder) == 1:
                port = int(remainder[0])
            elif len(remainder) == 2:
                port, datacenter = remainder

        upstream_definition["local_bind_port"] = int(port)

        if datacenter:
            upstream_definition["datacenter"] = datacenter

        # If there's a period in the destination name, this is a namespaced
        # service
        if "." in destination_name:
            service, namespace = destination_name.split(sep=".")
            upstream_definition.update(
                {"destination_name": service, "destination_namespace": namespace}
            )
        else:
            upstream_definition["destination_name"] = destination_name

        return upstream_definition

    def service_name(self) -> Union[str, None]:
        service_definition = self.service_config["service"]
        name = service_definition.get("name")
        return name

    def __init__(self, config: str):
        # Extra arguments to pass to 'consul connect envoy'
        self.connect_envoy_args = []  # type: list[str]

        # Extra arguments to pass to 'consul connect redirect-traffic'
        self.connect_redirect_traffic_args = []  # type: list[str]

        # Extra arguments to pass to `envoy`
        self.extra_envoy_args = ""

        # Read the service configuration file
        self.json_config = self.read_json_file(json_file=config)
        self.service_config = self.parse_service_config()

    def parse_service_config(self):
        # Prefix for each Connect annotation
        annotation_prefix = "consul.hashicorp.com/"

        connect_definition = ConnectDefinition(sidecar_service={})
        service_definition = ServiceDefinition(connect=connect_definition)
        proxy_config = ProxyConfig()

        if "annotations" not in self.json_config:
            sys.exit("Service configuration is missing annotations.")

        traffic_exclusion_options = frozenset(
            (
                "transparent-proxy-exclude-inbound-ports",
                "transparent-proxy-exclude-outbound-cidrs",
                "transparent-proxy-exclude-outbound-ports",
                "transparent-proxy-exclude-uids",
            )
        )

        annotations = self.json_config["annotations"]  # type: dict[str, str]
        service_metadata = {}  # type: dict[str, str]

        for annotation, value in annotations.items():
            if not annotation.startswith(annotation_prefix):
                continue

            option = self.removeprefix(annotation, annotation_prefix)

            # Set transparent proxy config in service registration
            if option == "connect-service":
                service_definition["name"] = value
            elif option == "connect-service-port":
                service_definition["port"] = int(value)
            elif option == "connect-service-upstreams":
                specified_upstreams = self.parse_csv(value)

                # Parsed upstream definitions
                upstreams = []  # type: list[UpstreamDefinition]

                for upstream in specified_upstreams:
                    upstream_declaration = self.parse_upstream_declaration(upstream)
                    # Ensure that returned value is not empty
                    if upstream_declaration:
                        upstreams.append(upstream_declaration)

                proxy_config["upstreams"] = upstreams

            elif option == "envoy-extra-args":
                self.extra_envoy_args = value
            elif option == "service-tags":
                service_definition["tags"] = self.parse_csv(value)
            elif option in traffic_exclusion_options:
                flag = self.removeprefix(option, "transparent-proxy-")
                # Remove trailing, plural 's' on flag
                flag = flag.rstrip("s")

                # Ensure value is a string
                value = str(value)
                exempt_values = self.parse_csv(value)
                for exemption in exempt_values:
                    self.add_redirect_traffic_arg(flag, exemption)
            elif option == "prometheus-scrape-path":
                self.add_connect_envoy_arg(option, value)
            elif option == "transparent-proxy":
                proxy_config["mode"] = "transparent" if bool(value) else "direct"
            elif option.startswith("service-meta-"):
                meta_key = self.removeprefix(option, "service-meta-")
                service_metadata[meta_key] = value

        # If service metadata exists, append it to service definition
        if service_metadata:
            service_definition["meta"] = service_metadata

        # If custom proxy parameters are configured, add them to the service
        # definition
        if proxy_config:
            connect_definition["sidecar_service"]["proxy"] = proxy_config

        self.service_registration = dict(service=service_definition)
        return self.service_registration

    def generate_connect_redirect_args(self):
        return " ".join(self.connect_redirect_traffic_args)

    def generate_connect_envoy_args(self):
        return " ".join(self.connect_envoy_args)

    def generate_envoy_args(self):
        return self.extra_envoy_args

    def generate_service_config(self):
        return json.dumps(self.service_config, indent=2, sort_keys=True)

    def read_json_file(self, json_file: str):
        try:
            with open(file=json_file) as fh:
                service_configuration = json.load(fp=fh)
        except:
            sys.exit("Unable to parse JSON registration.")

        return service_configuration


def start_systemd_process(name: str):
    if sys.platform != "linux":
        return

    import dbus

    sysbus = dbus.SystemBus()
    systemd1 = sysbus.get_object(
        bus_name="org.freedesktop.systemd1", object_path="/org/freedesktop/systemd1"
    )
    manager = dbus.Interface(
        object=systemd1, dbus_interface="org.freedesktop.systemd1.Manager"
    )

    # See https://wiki.freedesktop.org/www/Software/systemd/dbus/ for information
    # on each function
    manager.EnableUnitFiles([f"envoy@{name}.service"], False, True)
    manager.StartUnit(f"envoy@{name}.service", "fail")


def main():
    SERVICE_CONFIG_PATH = "/srv/consul/service-config.json"
    SERVICE_REGISTRATION_FILE = "/etc/consul.d/service-registration.json"

    EXTRA_ARGUMENTS_FILENAME = "/srv/consul/extra-args.json"

    SUPPORTED_OUTPUTS = ["connect-envoy", "envoy", "redirect", "service-registration"]

    parser = argparse.ArgumentParser(
        description="Generates a Consul service registration"
    )
    parser.add_argument("-f", "--filename", default=SERVICE_CONFIG_PATH)
    parser.add_argument(
        "--dry",
        action="store_true",
        help="Print to generated information to stdout",
    )
    parser.add_argument(
        "--type", choices=SUPPORTED_OUTPUTS, help="The type of information to output"
    )
    args = parser.parse_args()

    if not os.path.exists(args.filename):
        sys.exit(
            f"{args.filename} does not exist. Cannot properly initialize Consul client and proxy."
        )

    service_config = ServiceConfigParameters(config=args.filename)

    type_func_map = {
        "connect-envoy": service_config.generate_connect_envoy_args,
        "envoy": service_config.generate_envoy_args,
        "redirect": service_config.generate_connect_redirect_args,
        "service-registration": service_config.generate_service_config,
    }

    # Print the requested resource to stdout if running in dry mode
    if args.dry:
        if not args.type:
            parser.error("--dry requries --type to be specified.")

        func_to_exec = type_func_map[args.type]
        result = func_to_exec()

        if result:
            print(result)
        sys.exit()

    # Write the generated configurations to files
    extra_args = {}
    for key, func_to_exec in type_func_map.items():
        result = func_to_exec()

        if key == "service-registration":
            with open(SERVICE_REGISTRATION_FILE, mode="w+") as fh:
                fh.write(result)
        else:
            extra_args[key] = result

    # Write output of extra arguments to disk
    if extra_args:
        with open(EXTRA_ARGUMENTS_FILENAME, mode="w+") as fh:
            json.dump(extra_args, fp=fh, indent=2)

    # Lastly, try to start the systemd unit for the configured service
    service_name = service_config.service_name()
    if service_name:
        start_systemd_process(name=service_name)


if __name__ == "__main__":
    main()
