"""#3018合成作廢回覆的窄範圍啟動守門；不輸出啟動器或憑證。"""
from pathlib import Path
import re
import shlex
MESSAGE = '合成作廢回覆缺少已知必要欄位，或分支無法核對；請先驗外層MerchantID及內層原InvoiceNo，再啟動驗收服務。不得放寬產品核對。'
def invalid_reply_problem(source):
    if '/B2CInvoice/Invalid' not in source:
        return None
    branch = re.search(r"if\s*\(\s*path\s*===\s*['\"]/B2CInvoice/Invalid['\"]\s*\)\s*\{(.*?)\n  \}", source, re.S)
    if not branch:
        return MESSAGE
    text = branch.group(1)
    outer = re.search(r'JSON\.stringify\(\s*\{\s*MerchantID\s*:\s*config\.merchantId\s*,', text)
    inner = re.search(r'encryptEcpayInvoiceData\(\s*\{\s*RtnCode\s*:\s*1\s*,\s*InvoiceNo\s*:\s*request\.InvoiceNo\s*[,}]', text)
    return None if outer and inner else MESSAGE

def problem(text, cwd):
    for line in text.splitlines():
        try:
            words = shlex.split(line)
        except ValueError:
            continue
        if len(words) < 2 or Path(words[0]).name != 'node' or not re.fullmatch(r'start-auto-invoice\d*-atomic\.cjs', Path(words[1]).name):
            continue
        launcher = Path(words[1]); launcher = launcher if launcher.is_absolute() else Path(cwd) / launcher
        try:
            if launcher.stat().st_size > 131072: return MESSAGE
            references = re.findall(r"(/[^\s'\"]*provider-preload\.cjs)", launcher.read_text())
            if len(references) != 1: return MESSAGE
            preload = Path(references[0])
            if preload.stat().st_size > 131072: return MESSAGE
            return invalid_reply_problem(preload.read_text())
        except (OSError, UnicodeError):
            return MESSAGE
    return None
