"""PyMuPDF 的单一导入入口。

PyMuPDF 1.24+ 同时以 ``pymupdf`` 和旧名 ``fitz`` 暴露；各脚本若各自写一遍
fallback，会出现提示文本和行为不一致。这里集中处理导入与缺失提示。
"""

from __future__ import annotations

import sys

MISSING_HINT = "缺少 PyMuPDF；先运行 pip install -r requirements.txt。"

def require_pymupdf() -> object:
    """Return the PyMuPDF module, or exit with a readable message."""

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore[no-redef]
        except ImportError:
            print(MISSING_HINT, file=sys.stderr)
            raise SystemExit(2) from None
    return pymupdf
