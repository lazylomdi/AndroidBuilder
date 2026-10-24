import json
import tempfile
import unittest
from pathlib import Path
import ut_check

class ReadinessTests(unittest.TestCase):
    def test_missing_information_is_unknown(self):
        report = ut_check.assess_device("Sony", "Xperia R1", 2.0)
        self.assertEqual(report["assessment"], "UNKNOWN")
        self.assertIn("codename", report["missing_core_information"])
        self.assertTrue(all(x["status"] in ut_check.STATUSES for x in report["findings"]))

    def test_user_input_is_not_misrepresented_as_verified(self):
        report = ut_check.assess_device("Sony", "Xperia R1", 2.0, codename="candidate")
        by_key = {x["key"]: x for x in report["findings"]}
        self.assertEqual(by_key["manufacturer"]["status"], "CANDIDATE")
        self.assertIn("not independently verified", by_key["manufacturer"]["evidence"])
        self.assertEqual(by_key["kernel_source"]["status"], "UNKNOWN")

    def test_markdown_disclaims_functional_port(self):
        text = ut_check.render_markdown(ut_check.assess_device("Sony", "Xperia R1", 2.0))
        self.assertIn("No functional Ubuntu Touch port is established", text)
        self.assertIn("Physical device available", text)
        self.assertIn("## Compatibility summary", text)
        self.assertIn("Not enough information", text)
        self.assertIn("No independently verified Ubuntu Touch port evidence", text)

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            json_path = Path(temp) / "nested" / "report.json"
            md_path = Path(temp) / "report.md"
            result = ut_check.main(["--json-out", str(json_path), "--markdown-out", str(md_path)])
            self.assertEqual(result, 0)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["device"]["ram_gb"], 2.0)
            self.assertTrue(md_path.exists())

    def test_invalid_ram_is_rejected(self):
        with self.assertRaises(SystemExit):
            ut_check.main(["--ram-gb", "0"])

if __name__ == "__main__":
    unittest.main()
