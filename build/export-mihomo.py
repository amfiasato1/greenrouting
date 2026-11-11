#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path


DOMAIN_CATEGORIES = {"PRIVATE": "private", "CATEGORY-RU": "category-ru", "WHITELIST": "whitelist"}
IP_CATEGORIES = {"PRIVATE": "private-ip", "YANDEX": "yandex", "RU-WHITELIST": "ru-whitelist"}
DOMAIN_TYPES = {0: "DOMAIN-KEYWORD", 1: "DOMAIN-REGEX", 2: "DOMAIN-SUFFIX", 3: "DOMAIN"}


def varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError("truncated protobuf varint")
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError("protobuf varint overflows uint64")
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
    raise ValueError("invalid protobuf varint")


def fields(data: bytes):
    offset = 0
    while offset < len(data):
        tag, offset = varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("protobuf field number cannot be zero")
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire == 2:
            length, offset = varint(data, offset)
            if length > len(data) - offset:
                raise ValueError("truncated protobuf field")
            value = data[offset:offset + length]
            offset += length
        else:
            raise ValueError(f"unsupported protobuf wire type: {wire}")
        yield number, value


def scalar(items: list, number: int, expected: type, default=None):
    values = [value for field, value in items if field == number]
    if not values:
        return default
    if len(values) != 1 or not isinstance(values[0], expected):
        raise ValueError(f"invalid or duplicate protobuf field: {number}")
    return values[0]


def categories(source: Path, wanted: dict) -> dict[str, list]:
    result = {}
    for number, entry in fields(source.read_bytes()):
        if number != 1:
            continue
        if not isinstance(entry, bytes):
            raise ValueError("category entry must be a protobuf message")
        items = list(fields(entry))
        raw_name = scalar(items, 1, bytes)
        if not raw_name:
            raise ValueError("category name is missing")
        name = raw_name.decode("utf-8").upper()
        if name not in wanted:
            continue
        if name in result:
            raise ValueError(f"duplicate category: {name}")
        result[name] = items
    missing = wanted.keys() - result.keys()
    if missing:
        raise ValueError(f"missing categories: {', '.join(sorted(missing))}")
    return result


def domain_rules(items: list) -> list[str]:
    result = []
    for number, entry in items:
        if number != 2:
            continue
        if not isinstance(entry, bytes):
            raise ValueError("domain entry must be a protobuf message")
        domain = list(fields(entry))
        kind = scalar(domain, 1, int, 0)
        if kind not in DOMAIN_TYPES:
            raise ValueError(f"unsupported domain type: {kind}")
        raw_value = scalar(domain, 2, bytes)
        if not raw_value:
            raise ValueError("domain value is missing or empty")
        value = raw_value.decode("utf-8")
        if kind != 1 and "," in value:
            raise ValueError(f"comma is unsupported in domain type {kind}")
        result.append(f"{DOMAIN_TYPES[kind]},{value}")
    if not result:
        raise ValueError("empty domain category")
    return result


def ip_rules(items: list) -> list[str]:
    if scalar(items, 3, int, 0):
        raise ValueError("inverse GeoIP categories are unsupported")
    result = []
    for number, entry in items:
        if number != 2:
            continue
        if not isinstance(entry, bytes):
            raise ValueError("CIDR entry must be a protobuf message")
        cidr = list(fields(entry))
        packed = scalar(cidr, 1, bytes)
        prefix = scalar(cidr, 2, int, 0)
        if packed is None or len(packed) not in (4, 16):
            raise ValueError("CIDR address must contain 4 or 16 bytes")
        address = ipaddress.ip_address(packed)
        result.append(str(ipaddress.ip_network((address, prefix), strict=True)))
    if not result:
        raise ValueError("empty IP category")
    return result


def yaml_provider(payload: list[str]) -> str:
    return "payload:\n" + "".join(f"  - {json.dumps(value, ensure_ascii=False)}\n" for value in payload)


def export(geosite: Path, geoip: Path) -> dict[str, str]:
    output = {}
    for name, items in categories(geosite, DOMAIN_CATEGORIES).items():
        output[f"{DOMAIN_CATEGORIES[name]}.yaml"] = yaml_provider(domain_rules(items))
    for name, items in categories(geoip, IP_CATEGORIES).items():
        output[f"{IP_CATEGORIES[name]}.yaml"] = yaml_provider(ip_rules(items))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("geosite", type=Path)
    parser.add_argument("geoip", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    output = export(args.geosite, args.geoip)
    args.destination.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(output.items()):
        path = args.destination / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
        print(f"{path}: {len(content.splitlines()) - 1} rules")


if __name__ == "__main__":
    main()
