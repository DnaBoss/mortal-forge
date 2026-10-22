import json
from pathlib import Path
import subprocess
import sys
import unittest

GUARD = Path(__file__).with_name('collaboration_dispatch_guard.py')
REQUESTS = [
    '請用保存的原紅例與當前 helper 獨立核，保留正負對照。',
    '請先回報目前驗證結果，root 待結果再 launch。',
]


def decision(tool, message):
    result = subprocess.run([sys.executable, str(GUARD)], input=json.dumps({'tool_name': tool, 'tool_input': {'target': 'generic', 'message': message}}), text=True, capture_output=True, timeout=3)
    if result.returncode:
        raise AssertionError(result.stderr)
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    return output.get('hookSpecificOutput', {}).get('permissionDecision', 'allow'), output


class DispatchTests(unittest.TestCase):
    def test_confirmation_and_evidence_requests_require_waking_dispatch(self):
        for message in [
            '來源編號不同。請確認格式化是否改到既有來源，不能直接還原其他修改。',
            '請提供格式化命令與來源證據。',
            '請核對新版收據與原始內容。',
        ]:
            with self.subTest(message=message):
                self.assertEqual(decision('collaboration.send_message', message)[0], 'deny')
                self.assertEqual(decision('collaboration.followup_task', message)[0], 'allow')

    def test_two_observed_followup_requests_refused(self):
        for message in REQUESTS:
            with self.subTest(message=message):
                answer, output = decision('collaboration.send_message', message)
                self.assertEqual(answer, 'deny')
                self.assertIn('followup_task', output['hookSpecificOutput']['permissionDecisionReason'])

    def test_normalized_same_tool_refused(self):
        self.assertEqual(decision('collaboration__send_message', REQUESTS[0])[0], 'deny')

    def test_information_only_allowed(self):
        for message in ['原紅例與 helper 已保存，現在沒有來源程序。', '請知悉：root 正在驗證，尚未 launch。', '請勿啟動任何來源；本訊息只是告知限制。', '歷史原文：『請先回報結果』，當時沒有啟新回合。']:
            self.assertEqual(decision('collaboration.send_message', message)[0], 'allow')

    def test_punctuated_quoted_history_allowed_but_outside_work_refused(self):
        for quoted in [
            '『舊要求。請確認格式。』',
            '「舊要求。請核對來源。\n請提供收據。」',
            '“舊要求。請確認格式。”',
            '「外層『舊要求。請提供結果。』結束。」',
            '"Old request.\n請確認格式。"',
        ]:
            with self.subTest(quoted=quoted):
                history = f'歷史原文：{quoted}，本訊息只是紀錄。'
                self.assertEqual(decision('collaboration.send_message', history)[0], 'allow')
                direct = history + '請確認本次格式。'
                self.assertEqual(decision('collaboration.send_message', direct)[0], 'deny')
                self.assertEqual(decision('collaboration.followup_task', direct)[0], 'allow')
        self.assertEqual(decision('collaboration.send_message', '請確認「收據與來源」內容。')[0], 'deny')

    def test_followup_task_always_allowed(self):
        for tool in ['collaboration.followup_task', 'collaboration__followup_task']:
            self.assertEqual(decision(tool, REQUESTS[0])[0], 'allow')

    def test_non_collaboration_tool_allowed(self):
        for tool in ['Bash', 'other.send_message', 'collaboration.send_message_suffix']:
            self.assertEqual(decision(tool, REQUESTS[0])[0], 'allow')


if __name__ == '__main__':
    unittest.main()
