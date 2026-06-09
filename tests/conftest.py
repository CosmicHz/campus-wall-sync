"""
共享测试 fixtures

提供测试所需的通用 fixtures，避免每个测试文件重复设置。
"""

import pytest
import tempfile
import os
import json
from unittest.mock import patch


@pytest.fixture
def temp_config():
    """
    临时配置文件 fixture

    创建临时目录和配置文件，用于测试数据库和配置管理。
    测试结束后自动清理。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        config_path = os.path.join(tmpdir, "config.json")

        config_data = {
            "app": {
                "debug": False,
                "host": "0.0.0.0",
                "port": 5000,
                "log_level": "INFO"
            },
            "database": {
                "path": db_path,
                "echo": False
            },
            "halo": {
                "enabled": False,
                "api_url": "https://test-halo.com",
                "api_token": "test_token",
                "site_name": "test-site",
                "timeout": 30,
                "default_category": "",
                "default_tags": []
            },
            "tduck": {
                "enabled": True,
                "api_key": "test_api_key",
                "base_url": "https://x.tduckcloud.com",
                "field_ids": {
                    "class": "input1773416359370",
                    "name": "input1773416363353",
                    "content": "textarea1773416364971"
                },
                "sync": {
                    "enabled": True,
                    "interval_minutes": 5
                }
            },
            "review": {
                "enable_ai_review": False,
                "ai_review_type": "openai",
                "openai_api_key": "test_key"
            },
            "content_filter": {
                "replace_mode": True
            }
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        # 设置环境变量指向临时配置
        old_config_path = os.environ.get("CONFIG_PATH")
        os.environ["CONFIG_PATH"] = config_path

        yield {
            "tmpdir": tmpdir,
            "db_path": db_path,
            "config_path": config_path,
            "config_data": config_data
        }

        # 清理环境变量
        if old_config_path:
            os.environ["CONFIG_PATH"] = old_config_path
        elif "CONFIG_PATH" in os.environ:
            del os.environ["CONFIG_PATH"]


@pytest.fixture
def reset_config():
    """
    重置 Config 单例 fixture

    确保每个测试使用新的配置实例。
    """
    from src.config import Config
    Config.reset()
    yield
    Config.reset()


@pytest.fixture
def reset_database():
    """
    重置数据库连接 fixture

    确保每个测试使用独立的数据库连接。
    """
    from src.database import reset_db, close_db
    reset_db()
    yield
    close_db()
    reset_db()


@pytest.fixture
def mock_requests():
    """
    Mock requests 库 fixture

    用于测试 API 客户端，避免真实 HTTP 请求。
    """
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post, \
         patch("requests.put") as mock_put, \
         patch("requests.request") as mock_request:
        yield {
            "get": mock_get,
            "post": mock_post,
            "put": mock_put,
            "request": mock_request
        }


@pytest.fixture
def sample_post_data():
    """
    示例投稿数据 fixture

    提供标准的投稿数据结构，用于测试解析和过滤。
    """
    return {
        "title": "高一(1)班-小明的投稿",
        "content": "这是一条测试投稿内容，用于验证功能。",
        "class_name": "高一(1)班",
        "user_name": "小明",
        "wx_nickname": "xiaoming",
        "wx_openid": "test_openid_123",
        "wx_avatar": "https://example.com/avatar.jpg",
        "submit_address": "广东省-广州市",
        "submit_time": "2026-03-14 00:14:05",
        "tags": ["高一(1)班"],
        "tduck_id": 623899,
        "tduck_serial": 4
    }


@pytest.fixture
def sample_webhook_data():
    """
    示例 Webhook 数据 fixture

    提供标准的 tduck Webhook 数据结构。
    """
    return {
        "input1773416359370": "高一十三班",
        "input1773416363353": "小明",
        "textarea1773416364971": "我喜欢小红",
        "dataId": "22c480500000000003de288e992042b3",
        "formKey": "y0ccu2pa",
        "serialNumber": 4,
        "submitAddress": "广东省-广州市",
        "wxOpenId": "test_openid_123",
        "wxUserInfo": {
            "nickname": "xiaoming",
            "openid": "test_openid_123",
            "headImgUrl": "https://example.com/avatar.jpg"
        },
        "id": 623899,
        "createTime": "2026-03-14 00:14:05",
        "eventType": "form_data_add"
    }