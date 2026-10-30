import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description='檢查 PDF 每頁是否有不透明底色')
    parser.add_argument('pdf', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='pdf-background-check-') as folder:
        subprocess.run(['pdftocairo', '-png', '-transp', '-scale-to', '512', str(args.pdf.resolve()), str(Path(folder) / 'page')], check=True, timeout=180)
        pages = sorted(Path(folder).glob('page-*.png'))
        if not pages:
            raise RuntimeError('PDF 沒有可檢查的頁面')
        failed = []
        for i, page in enumerate(pages, 1):
            with Image.open(page) as image:
                alpha = image.convert('RGBA').getchannel('A')
                if alpha.crop((1, 1, alpha.width - 1, alpha.height - 1)).getextrema()[0] != 255:
                    failed.append(i)
        if failed:
            print(f'未通過：第 {failed} 頁有透明區域')
            return 1
        print(f'通過：{len(pages)} 頁都有不透明底色')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
