#!/usr/bin/env python3
"""审计逐页 TeX 的语义所有权、跨页环境结构与集中职责归属。

命令行入口；实现位于同目录的 ``semantics`` 包。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from semantics.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
