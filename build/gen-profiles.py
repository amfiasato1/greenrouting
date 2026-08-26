#!/usr/bin/env python3
"""Generate Happ/Incy routing profiles (JSON + deeplink files).

The geo URLs are pinned to a tag of THIS repository so jsDelivr serves
immutable, cache-safe artifacts. Call with --tag after the release commit;
--last-updated defaults to the current epoch so clients re-fetch the geofiles.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPO = "amfiasato1/greenrouting"
PROFILE_NAME = "Green Routing"

DNS_HOSTS = {
    "lkfl2.nalog.ru": "213.24.64.175",
    "lknpd.nalog.ru": "213.24.64.181",
}


def profile(tag: str, last_updated: int, *, jsonsub: bool) -> dict:
    return {
        "Name": PROFILE_NAME,
        "GlobalProxy": "true",
        # Chunked per-section copies save nothing on a ~60 KB file but add an
        # extra processing step between download and use — a known source of
        # "section missing" failures when that step glitches.
        "UseChunkFiles": "false",
        "RemoteDns": "8.8.8.8",
        "DomesticDns": "77.88.8.8",
        "RemoteDNSType": "DoH",
        "RemoteDNSDomain": "https://8.8.8.8/dns-query",
        "RemoteDNSIP": "8.8.8.8",
        "DomesticDNSType": "DoH",
        "DomesticDNSDomain": "https://77.88.8.8/dns-query",
        "DomesticDNSIP": "77.88.8.8",
        "Geoipurl": f"https://cdn.jsdelivr.net/gh/{REPO}@{tag}/release/geoip.dat",
        "Geositeurl": f"https://cdn.jsdelivr.net/gh/{REPO}@{tag}/release/geosite.dat",
        "LastUpdated": str(last_updated),
        "DnsHosts": DNS_HOSTS,
        "RouteOrder": "block-proxy-direct",
        "DirectSites": [] if jsonsub else [
            "geosite:private",
            "geosite:category-ru",
            "geosite:whitelist",
        ],
        # Many services talk to raw IPs without domain matches: Yandex-owned
        # ranges plus the runetfreedom mobile whitelist of known-good RU
        # service subnets (Yandex Cloud, VK, Mail.ru CDNs, ...) ride along
        # with RFC1918 in DIRECT.
        "DirectIp": [] if jsonsub else [
            "geoip:private",
            "geoip:yandex",
            "geoip:ru-whitelist",
        ],
        "ProxySites": [],
        "ProxyIp": [],
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
    }


def write_profiles(tag: str, last_updated: int) -> None:
    for client, scheme in (("HAPP", "happ"), ("INCY", "incy")):
        client_dir = ROOT / client
        for variant in ("DEFAULT", "JSONSUB"):
            data = profile(tag, last_updated, jsonsub=(variant == "JSONSUB"))
            compact = json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"
            payload = base64.b64encode(compact.encode()).decode()

            json_path = client_dir / f"{variant}.JSON"
            json_path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")

            deeplink_path = client_dir / f"{variant}.DEEPLINK"
            deeplink_path.write_text(f"{scheme}://routing/onadd/{payload}\n")
            print(f"{deeplink_path.relative_to(ROOT)} ({len(payload)} b64 chars)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True, help="git tag to pin geo URLs to")
    parser.add_argument(
        "--last-updated",
        type=int,
        default=lambda: int(time.time()),
        help="LastUpdated epoch (default: now)",
    )
    args = parser.parse_args()

    last_updated = (
        args.last_updated if isinstance(args.last_updated, int) else args.last_updated()
    )
    write_profiles(args.tag, last_updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
