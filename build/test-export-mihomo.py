import hashlib
import importlib.util
import ipaddress
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mihomo_exporter", ROOT / "build/export-mihomo.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    return varint((number << 3) | 2) + varint(len(value)) + value


def domain(kind, value):
    return field(2, field(1, kind) + field(2, value.encode()))


def cidr(address, prefix):
    return field(2, field(1, ipaddress.ip_address(address).packed) + field(2, prefix))


def decode_yaml(content):
    return [json.loads(line[4:]) for line in content.splitlines()[1:]]


class ExportTests(unittest.TestCase):
    def test_all_domain_types_and_regex_are_preserved(self):
        regex = r'^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$'
        entries = domain(0, "keyword") + domain(1, regex) + domain(2, "example.org") + domain(3, "only.example.org")
        self.assertEqual(exporter.domain_rules(list(exporter.fields(entries))), [
            "DOMAIN-KEYWORD,keyword", f"DOMAIN-REGEX,{regex}",
            "DOMAIN-SUFFIX,example.org", "DOMAIN,only.example.org",
        ])

    def test_proto_default_domain_type_is_keyword(self):
        entries = field(2, field(2, b"keyword"))
        self.assertEqual(exporter.domain_rules(list(exporter.fields(entries))), ["DOMAIN-KEYWORD,keyword"])

    def test_yaml_roundtrip_escapes(self):
        payload = ['DOMAIN-REGEX,^a\\d{1,3}["#:]$', 'DOMAIN,пример.рф']
        self.assertEqual(decode_yaml(exporter.yaml_provider(payload)), payload)

    def test_ipv4_and_ipv6_are_preserved(self):
        entries = cidr("10.0.0.0", 8) + cidr("fc00::", 7)
        self.assertEqual(exporter.ip_rules(list(exporter.fields(entries))), ["10.0.0.0/8", "fc00::/7"])

    def test_inverse_ip_category_fails(self):
        with self.assertRaisesRegex(ValueError, "inverse"):
            exporter.ip_rules(list(exporter.fields(field(3, 1) + cidr("10.0.0.0", 8))))

    def test_invalid_ip_categories_fail(self):
        for bad in [cidr("10.0.0.0", 33), cidr("10.0.0.1", 8), field(2, field(1, b"123")), field(2, field(2, 8))]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                exporter.ip_rules(list(exporter.fields(bad)))

    def test_unknown_domain_type_and_empty_values_fail(self):
        for bad in [domain(9, "example.org"), domain(3, ""), field(2, field(1, 3)), domain(2, "example.org,no-resolve")]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                exporter.domain_rules(list(exporter.fields(bad)))

    def test_truncated_and_invalid_protobuf_fail(self):
        for bad in [b"\x80", b"\x0a\x03ab", b"\x00", b"\x0f", b"\xff" * 10, b"\x80" * 10 + b"\x00"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                list(exporter.fields(bad))

    def test_missing_duplicate_and_empty_categories_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.dat"
            category = field(1, field(1, b"PRIVATE") + domain(3, "example.org"))
            source.write_bytes(category)
            with self.assertRaisesRegex(ValueError, "missing"):
                exporter.categories(source, exporter.DOMAIN_CATEGORIES)
            source.write_bytes(category + category)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                exporter.categories(source, {"PRIVATE": "private"})
        with self.assertRaisesRegex(ValueError, "empty"):
            exporter.domain_rules([])
        with self.assertRaisesRegex(ValueError, "empty"):
            exporter.ip_rules([])

    def test_real_artifacts_preserve_rules_and_inputs(self):
        paths = list((ROOT / "HAPP").glob("*")) + list((ROOT / "INCY").glob("*")) + list((ROOT / "release").glob("*.dat")) + [ROOT / "release/SHA256SUMS"]
        before = {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}
        result = exporter.export(ROOT / "release/geosite.dat", ROOT / "release/geoip.dat")
        self.assertEqual(set(result), {"private.yaml", "category-ru.yaml", "whitelist.yaml", "private-ip.yaml", "yandex.yaml", "ru-whitelist.yaml"})
        self.assertIn("DOMAIN-SUFFIX,ru", decode_yaml(result["category-ru.yaml"]))
        self.assertIn("DOMAIN-SUFFIX,ipify.org", decode_yaml(result["whitelist.yaml"]))
        self.assertIn("DOMAIN-REGEX,^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", decode_yaml(result["private.yaml"]))
        self.assertIn("DOMAIN,router.asus.com", decode_yaml(result["private.yaml"]))
        self.assertNotIn("DOMAIN-SUFFIX,router.asus.com", decode_yaml(result["private.yaml"]))
        self.assertTrue(any(ipaddress.ip_address("77.88.8.8") in ipaddress.ip_network(n) for n in decode_yaml(result["yandex.yaml"])))
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).digest() for path in paths})


if __name__ == "__main__":
    unittest.main()
