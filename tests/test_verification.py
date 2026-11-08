"""历史 Bug 回归测试 (接入 pytest, 此前从未被任何流程调用)。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from formatter_core.verification import run_strict_test


def test_legacy_bug_regressions():
    """Bug L / Bug I / Bug M / P2 四项历史缺陷必须持续保持修复状态。"""
    run_strict_test()
