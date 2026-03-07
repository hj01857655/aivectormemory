"""验证 install.py STEERING_CONTENT 包含关键章节"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aivectormemory.install import STEERING_CONTENT


def test_steering_has_task_check():
    assert "未完成" in STEERING_CONTENT or "不为 completed" in STEERING_CONTENT
    assert "task" in STEERING_CONTENT




def test_steering_has_code_review():
    assert "操作前检查" in STEERING_CONTENT


def test_steering_has_track_workflow():
    assert "问题追踪" in STEERING_CONTENT
    assert "track create" in STEERING_CONTENT
    assert "track archive" in STEERING_CONTENT
