"""
Halo API 客户端测试

测试 halo_client.py 的核心功能：
- API 请求
- 文章创建
- 文章更新
- 连接测试
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from src.services.halo_client import HaloClient


class TestHaloClientInit:
    """测试客户端初始化"""

    def test_client_initializes_with_config(self, temp_config, reset_config):
        """测试客户端从配置初始化"""
        client = HaloClient()
        # 注意：config.json 中 api_url 是 "https://test-halo-site.com"
        assert client.api_url == "https://test-halo-site.com"
        assert client.api_token == "test_token"
        assert client.site_name == "test-site"
        assert client.timeout == 30

    def test_client_default_values(self, temp_config, reset_config):
        """测试默认值"""
        # 使用 temp_config fixture，它已经设置了配置
        client = HaloClient()
        # 默认值从配置读取
        assert client.default_category == ""
        assert client.default_tags == []


class TestTestConnection:
    """测试连接测试"""

    @patch("requests.request")
    def test_connection_success(self, mock_request, temp_config, reset_config):
        """测试连接成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_request.return_value = mock_response

        client = HaloClient()
        result = client.test_connection()

        assert result["status"] == "connected"
        assert "连接成功" in result["message"]

    @patch("requests.request")
    def test_connection_failure(self, mock_request, temp_config, reset_config):
        """测试连接失败"""
        import requests
        mock_request.side_effect = requests.RequestException("网络错误")

        client = HaloClient()
        result = client.test_connection()

        assert result["status"] == "error"
        assert "网络错误" in result["message"]


class TestCreatePost:
    """测试创建文章"""

    @patch("requests.request")
    def test_create_post_success(self, mock_request, temp_config, reset_config):
        """测试成功创建文章"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "metadata": {"name": "test-post-uuid"},
            "spec": {"title": "测试文章"}
        }
        mock_request.return_value = mock_response

        client = HaloClient()
        result = client.create_post(
            title="测试文章",
            content="测试内容",
            publish=False
        )

        assert result["metadata"]["name"] == "test-post-uuid"
        mock_request.assert_called()

    @patch("requests.request")
    def test_create_post_with_publish(self, mock_request, temp_config, reset_config):
        """测试创建并发布文章"""
        # 创建请求
        mock_create = Mock()
        mock_create.status_code = 200
        mock_create.json.return_value = {
            "metadata": {"name": "test-uuid"},
            "spec": {"title": "测试"}
        }

        # 发布请求
        mock_publish = Mock()
        mock_publish.status_code = 200

        mock_request.side_effect = [mock_create, mock_publish]

        client = HaloClient()
        result = client.create_post(
            title="测试文章",
            content="测试内容",
            publish=True
        )

        assert mock_request.call_count == 2

    @patch("requests.request")
    def test_create_post_with_custom_tags(self, mock_request, temp_config, reset_config):
        """测试自定义标签"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"metadata": {"name": "test"}}
        mock_request.return_value = mock_response

        client = HaloClient()
        client.create_post(
            title="测试",
            content="内容",
            tags=["自定义标签"],
            publish=False
        )

        # 验证请求体包含自定义标签
        call_args = mock_request.call_args
        request_data = call_args[1]["json"]
        assert "自定义标签" in request_data["spec"]["tags"]


class TestUpdatePost:
    """测试更新文章"""

    @patch("requests.request")
    def test_update_post_success(self, mock_request, temp_config, reset_config):
        """测试成功更新文章"""
        # 获取草稿
        mock_draft = Mock()
        mock_draft.status_code = 200
        mock_draft.json.return_value = {
            "metadata": {"name": "test-uuid", "annotations": {}},
            "spec": {"title": "旧标题"}
        }

        # 更新草稿
        mock_update = Mock()
        mock_update.status_code = 200
        mock_update.json.return_value = {
            "metadata": {"name": "test-uuid"},
            "spec": {"title": "新标题"}
        }

        mock_request.side_effect = [mock_draft, mock_update]

        client = HaloClient()
        result = client.update_post(
            post_name="test-uuid",
            title="新标题",
            content="新内容"
        )

        assert mock_request.call_count == 2


class TestDeletePost:
    """测试删除文章"""

    @patch("requests.request")
    def test_delete_post_success(self, mock_request, temp_config, reset_config):
        """测试成功删除文章"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = HaloClient()
        result = client.delete_post("test-uuid")

        assert result is True

    @patch("requests.request")
    def test_delete_post_failure(self, mock_request, temp_config, reset_config):
        """测试删除失败"""
        import requests
        mock_request.side_effect = requests.RequestException("删除失败")

        client = HaloClient()
        result = client.delete_post("test-uuid")

        assert result is False


class TestListCategories:
    """测试获取分类列表"""

    @patch("requests.request")
    def test_list_categories_success(self, mock_request, temp_config, reset_config):
        """测试成功获取分类"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "metadata": {"name": "cat-1"},
                    "spec": {"displayName": "分类1", "slug": "cat1"}
                },
                {
                    "metadata": {"name": "cat-2"},
                    "spec": {"displayName": "分类2", "slug": "cat2"}
                }
            ]
        }
        mock_request.return_value = mock_response

        client = HaloClient()
        categories = client.list_categories()

        assert len(categories) == 2
        assert categories[0]["name"] == "cat-1"
        assert categories[0]["displayName"] == "分类1"


class TestListTags:
    """测试获取标签列表"""

    @patch("requests.request")
    def test_list_tags_success(self, mock_request, temp_config, reset_config):
        """测试成功获取标签"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "metadata": {"name": "tag-1"},
                    "spec": {"displayName": "标签1", "slug": "tag1"}
                }
            ]
        }
        mock_request.return_value = mock_response

        client = HaloClient()
        tags = client.list_tags()

        assert len(tags) == 1
        assert tags[0]["name"] == "tag-1"


class TestGetHeaders:
    """测试请求头生成"""

    def test_headers_contain_auth(self, temp_config, reset_config):
        """测试请求头包含认证信息"""
        client = HaloClient()
        headers = client._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"