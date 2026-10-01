#!/usr/bin/env python3
"""Export the mobile IPv4 whitelist as plain CIDRs, without modifying DAT files."""

import argparse
import importlib.util
import ipaddress
from pathlib import Path


def export(source: Path) -> str:
    spec = importlib.util.spec_from_file_location("dat_fields", Path(__file__).with_name("filter-dat.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    wanted = {"RU-WHITELIST", "YANDEX"}
    found = set()
    networks = []
    for number, entry in module.fields(source.read_bytes()):
        if number != 1:
            continue
        fields = list(module.fields(entry))
        name = next((value.decode() for field, value in fields if field == 1), "")
        if name not in wanted:
            continue
        found.add(name)
        if any(field == 3 and value for field, value in fields):
            raise ValueError(f"inverse category is unsupported: {name}")
        category = []
        for field, cidr in fields:
            if field != 2:
                continue
            parts = dict(module.fields(cidr))
            packed, prefix = parts[1], parts.get(2, 0)
            address = ipaddress.ip_address(packed)
            network = ipaddress.ip_network((address, prefix), strict=False)
            if network.version == 4:
                if network.prefixlen == 0 or not network.network_address.is_global:
                    raise ValueError(f"unexpected whitelist network: {network}")
                category.append(network)
        if not category:
            raise ValueError(f"empty IPv4 category: {name}")
        networks.extend(category)
    if found != wanted:
        raise ValueError(f"missing categories: {', '.join(sorted(wanted - found))}")
    return "".join(f"{network}\n" for network in ipaddress.collapse_addresses(networks))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    content = export(args.source)
    temporary = args.destination.with_suffix(args.destination.suffix + ".tmp")
    temporary.write_text(content)
    temporary.replace(args.destination)
