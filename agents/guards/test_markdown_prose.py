import unittest
import write_guard


class MarkdownProse(unittest.TestCase):
    def rule(self, item):
        return write_guard.verdict({"tool_input": item})[0]

    def test_observed_phrases_denied_in_added_markdown(self):
        for phrase in ["\u5404\u7ec4", "\u5206\u522b", "\u6307\u6570\u5206\u5e03", "\u4fdd\u5b58\u8be5", "\u5ba3\u79f0", "\u786e\u8ba4", "\u53cc\u7ad9"]:
            with self.subTest(phrase=phrase):
                patch = "*** Begin Patch\n*** Update File: /tmp/doc.md\n@@\n+" + phrase + "\n*** End Patch"
                self.assertEqual(self.rule({"patch": patch}), "markdown-prose")
                self.assertEqual(self.rule({"input": patch}), "markdown-prose")

    def test_traditional_correction_allowed(self):
        patch = "*** Begin Patch\n*** Update File: /tmp/doc.md\n@@\n-\u5404\u7ec4\n+各組分布，分別確認，不宣稱雙站完成\n*** End Patch"
        self.assertIsNone(self.rule({"patch": patch}))

    def test_existing_context_not_rejected(self):
        patch = "*** Begin Patch\n*** Update File: /tmp/doc.md\n@@\n \u5404\u7ec4\n+已保存\n*** End Patch"
        self.assertIsNone(self.rule({"patch": patch}))

    def test_code_and_verbatim_quote_keep_original(self):
        patch = "*** Begin Patch\n*** Add File: /tmp/doc.md\n+```text\n+\u5404\u7ec4\n+```\n+> \u5ba3\u79f0\n*** End Patch"
        self.assertIsNone(self.rule({"patch": patch}))

    def test_direct_markdown_write_checked(self):
        self.assertEqual(self.rule({"file_path": "/tmp/doc.md", "content": "\u53cc\u7ad9"}), "markdown-prose")

    def test_nonmarkdown_and_removed_text_unchanged(self):
        self.assertIsNone(self.rule({"file_path": "/tmp/source.rs", "new_string": "\u5404\u7ec4"}))
        self.assertIsNone(self.rule({"file_path": "/tmp/doc.md", "old_string": "\u5404\u7ec4", "new_string": "各組"}))


if __name__ == "__main__":
    unittest.main()
