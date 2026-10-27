import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


source = Path(os.environ.get("RECALL_RENDERER", Path(__file__).with_name("render_recall_pdf.py")))
spec = importlib.util.spec_from_file_location("renderer", source)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class HandoffPdfTests(unittest.TestCase):
    def render(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        output = Path(directory.name) / "report.pdf"
        renderer.render(data, output)
        content = subprocess.check_output(["pdftotext", "-layout", str(output), "-"], text=True)
        return output, content

    def example(self):
        reference = Path(__file__).parents[1] / "references/handoff.md"
        return json.loads(reference.read_text().split("```json\n")[1].split("```", 1)[0])

    def test_documented_example_retains_handoff(self):
        data = self.example()
        _, content = self.render(data)
        for section in data["sections"]:
            self.assertIn(section["heading"], content)
            for entry in section["entries"]:
                self.assertIn(entry["title"], content)
                self.assertIn(entry["detail"], content)

    def test_long_handoff_keeps_last_item_and_stays_on_page(self):
        data = self.example()
        detail = "保留未完成工作，不要重新啟動背景程序。" * 90 + "最後仍須人工驗收。"
        data["sections"][0]["entries"] = [
            {"title": f"接手項目{i}", "detail": detail} for i in range(8)
        ]
        output, content = self.render(data)
        self.assertEqual(content.count("最後仍須人工驗收。"), 8)
        self.assertIn("接手項目7", content)
        self.assertGreater(content.count("\f"), 2)
        xml = subprocess.check_output(["pdftotext", "-bbox", str(output), "-"], text=True)
        root = ET.fromstring(xml)
        for page in root.iter("{http://www.w3.org/1999/xhtml}page"):
            for word in page.iter("{http://www.w3.org/1999/xhtml}word"):
                self.assertGreaterEqual(float(word.attrib["xMin"]), 0)
                self.assertGreaterEqual(float(word.attrib["yMin"]), 0)
                self.assertLessEqual(float(word.attrib["xMax"]), float(page.attrib["width"]))
                self.assertLessEqual(float(word.attrib["yMax"]), float(page.attrib["height"]))

    def test_empty_handoff_is_rejected(self):
        data = self.example()
        data["sections"] = []
        with self.assertRaises(ValueError):
            self.render(data)

    def test_legacy_report_still_renders(self):
        _, content = self.render({"title": "舊報告", "timestamp": "2026-10-25", "summary": "尚未部署"})
        self.assertIn("尚未部署", content)


if __name__ == "__main__":
    unittest.main()
