import subprocess
import unittest
from unittest.mock import patch

import device_inspector


class DeviceInspectorTests(unittest.TestCase):
    def test_parse_getprop(self):
        props = device_inspector._parse_getprop(
            "[ro.product.model]: [Example Phone]\n[ro.build.version.release]: [13]\n"
            "[ro.empty]: []\n"
        )
        self.assertEqual(props["ro.product.model"], "Example Phone")
        self.assertEqual(props["ro.build.version.release"], "13")
        self.assertNotIn("ro.empty", props)

    @patch("device_inspector.shutil.which", return_value=None)
    def test_missing_adb_is_reported(self, _which):
        result = device_inspector.inspect_device()
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("ADB was not found", result["message"])

    @patch("device_inspector.shutil.which", return_value="adb")
    @patch("device_inspector._run")
    def test_no_connected_device(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            ["adb", "devices", "-l"], 0, "List of devices attached\n", ""
        )
        result = device_inspector.inspect_device()
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("No phone detected", result["message"])

    @patch("device_inspector.shutil.which", return_value="adb")
    @patch("device_inspector._run")
    def test_multiple_devices_require_serial(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            ["adb", "devices", "-l"], 0,
            "List of devices attached\nABC device product:a model:a\nXYZ device product:b model:b\n", ""
        )
        result = device_inspector.inspect_device()
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("--serial SERIAL", result["message"])
        self.assertEqual(len(result["devices"]), 2)

    @patch("device_inspector.shutil.which", return_value="adb")
    @patch("device_inspector._run")
    def test_successful_read_only_inspection(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess(["adb", "devices", "-l"], 0,
                "List of devices attached\nABC device product:demo model:Demo\n", ""),
            subprocess.CompletedProcess(["adb", "shell", "getprop"], 0,
                "[ro.product.manufacturer]: [Example]\n[ro.product.model]: [Demo Phone]\n"
                "[ro.product.device]: [demo]\n[ro.build.version.release]: [13]\n"
                "[ro.product.cpu.abi]: [arm64-v8a]\n", ""),
            subprocess.CompletedProcess(["adb", "shell", "cat"], 0, "MemTotal:       2097152 kB\n", ""),
            subprocess.CompletedProcess(["adb", "shell", "uname"], 0, "5.10.1\n", ""),
        ]
        result = device_inspector.inspect_device()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["device"]["manufacturer"], "Example")
        self.assertEqual(result["device"]["codename"], "demo")
        self.assertEqual(result["device"]["kernel_version"], "5.10.1")
        self.assertEqual(result["device"]["ram_gb"], 2.0)
        self.assertIsNone(result["device"]["bootloader_unlock"])
        self.assertIn("No device files or settings were changed.", result["limitations"])
        self.assertIn("Bootloader unlock eligibility/status is not inferred from these properties.", result["limitations"])


if __name__ == "__main__":
    unittest.main()
