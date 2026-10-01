import hashlib
import importlib.util
import ipaddress
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exporter", ROOT / "build/export-whitelist.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def test_existing_artifacts_are_unchanged(self):
        paths = list((ROOT / "HAPP").glob("*")) + list((ROOT / "INCY").glob("*")) + list((ROOT / "release").glob("*.dat")) + [ROOT / "release/SHA256SUMS"]
        before = {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}
        result = exporter.export(ROOT / "release/geoip.dat")
        networks = [ipaddress.ip_network(line) for line in result.splitlines()]
        self.assertTrue(networks)
        self.assertTrue(all(n.version == 4 and n.prefixlen > 0 for n in networks))
        self.assertTrue(any(ipaddress.ip_address("77.88.8.8") in n for n in networks))
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).digest() for path in paths})

    def test_missing_categories_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.dat"
            path.write_bytes(b"")
            with self.assertRaises(ValueError):
                exporter.export(path)


if __name__ == "__main__":
    unittest.main()
