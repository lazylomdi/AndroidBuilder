"""Guardrails for the reviewed device compatibility catalog."""
import json
import unittest
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "data" / "device_catalog.json"


class DeviceCatalogTests(unittest.TestCase):
    def test_known_user_devices_are_unverified_not_supported(self):
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        devices = data["devices"]
        self.assertGreaterEqual(len(devices), 2)
        by_model = {model: entry for entry in devices for model in entry["model_ids"]}
        for model in ("G2199", "SM-A042F"):
            self.assertIn(model, by_model)
            self.assertEqual(by_model[model]["status"], "INVESTIGATING")
            self.assertEqual(by_model[model]["ubuntu_touch_port"], "UNKNOWN")
            self.assertIsNone(by_model[model]["installation_procedure"])
            self.assertIsNone(by_model[model]["recovery_procedure"])

    def test_catalog_does_not_claim_support_without_evidence(self):
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        for device in data["devices"]:
            if device["status"] != "SUPPORTED":
                self.assertIsNone(device["installation_procedure"])


if __name__ == "__main__":
    unittest.main()
