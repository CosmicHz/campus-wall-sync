"""
tduck API 客户端测试

测试 tduck_client.py 的核心功能：
- API 请求
- 字段获取
- 数据同步
- Webhook 验证
"""

import pytest
from unittest.mock import patch, Mock, MagicMock, PropertyMock
from src.services.tduck_client import TduckClient
from src.config import Config


class TestTduckClientInit:
    """测试客户端初始化"""

    def test_client_initializes_with_config(self):
        """测试客户端从配置初始化"""
        # 使用 PropertyMock patch property
        mock_tduck = {
            "base_url": "https://x.tduckcloud.com",
            "api_key": "test_api_key",
            "timeout": 30
        }
        with patch.object(Config, 'tduck', new_callable=PropertyMock, return_value=mock_tduck):
            client = TduckClient()
            assert client.base_url == "https://x.tduckcloud.com"
            assert client.api_key == "test_api_key"
            assert client.timeout == 30

    def test_client_default_timeout(self):
        """测试默认超时时间"""
        mock_tduck = {"timeout": 30}
        with patch.object(Config, 'tduck', new_callable=PropertyMock, return_value=mock_tduck):
            client = TduckClient()
            assert client.timeout == 30


class TestGetFormFields:
    """测试获取表单字段"""

    @patch("requests.get")
    def test_get_form_fields_success(self, mock_get, temp_config, reset_config):
        """测试成功获取表单字段"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "fields": [
                    {"value": "input123", "label": "班级", "type": "INPUT"},
                    {"value": "textarea456", "label": "内容", "type": "TEXTAREA"},
                ]
            }
        }
        mock_get.return_value = mock_response

        client = TduckClient()
        fields = client.get_form_fields()

        assert len(fields) == 2
        assert fields[0]["label"] == "班级"
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_get_form_fields_api_error(self, mock_get, temp_config, reset_config):
        """测试 API 返回错误"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 500,
            "msg": "服务器错误"
        }
        mock_get.return_value = mock_response

        client = TduckClient()
        with pytest.raises(ValueError, match="获取字段失败"):
            client.get_form_fields()

    @patch("requests.get")
    def test_get_form_fields_network_error(self, mock_get, temp_config, reset_config):
        """测试网络请求失败"""
        import requests
        mock_get.side_effect = requests.RequestException("网络错误")

        client = TduckClient()
        with pytest.raises(requests.RequestException):
            client.get_form_fields()


class TestGetFormData:
    """测试获取表单数据"""

    @patch("requests.get")
    def test_get_form_data_success(self, mock_get, temp_config, reset_config):
        """测试成功获取表单数据"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "records": [
                    {"id": 1, "serialNumber": 1},
                    {"id": 2, "serialNumber": 2},
                ],
                "total": 2
            }
        }
        mock_get.return_value = mock_response

        client = TduckClient()
        data = client.get_form_data()

        assert data["total"] == 2
        assert len(data["records"]) == 2

    @patch("requests.get")
    def test_get_all_form_data(self, mock_get, temp_config, reset_config):
        """测试获取所有数据"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "records": [{"id": i} for i in range(10)],
                "total": 10
            }
        }
        mock_get.return_value = mock_response

        client = TduckClient()
        records = client.get_all_form_data()

        assert len(records) == 10


class TestValidateWebhookPayload:
    """测试 Webhook 数据验证"""

    def test_valid_webhook_with_original_data(self, temp_config, reset_config):
        """测试包含 originalData 的有效数据"""
        payload = {
            "id": 123,
            "originalData": {
                "input123": "班级",
                "textarea456": "内容"
            }
        }
        client = TduckClient()
        assert client.validate_webhook_payload(payload) is True

    def test_valid_webhook_with_direct_fields(self, temp_config, reset_config):
        """测试直接包含字段的有效数据"""
        payload = {
            "id": 123,
            "input123": "班级",
            "textarea456": "内容"
        }
        client = TduckClient()
        assert client.validate_webhook_payload(payload) is True

    def test_invalid_webhook_missing_data(self, temp_config, reset_config):
        """测试缺少数据字段"""
        payload = {
            "id": 123,
            "serialNumber": 1
        }
        client = TduckClient()
        assert client.validate_webhook_payload(payload) is False

    def test_invalid_webhook_not_dict(self, temp_config, reset_config):
        """测试非字典类型数据"""
        client = TduckClient()
        assert client.validate_webhook_payload("not a dict") is False
        assert client.validate_webhook_payload(None) is False
        assert client.validate_webhook_payload([]) is False

    def test_valid_webhook_with_radio_field(self, temp_config, reset_config):
        """测试包含 radio 字段的有效数据"""
        payload = {
            "id": 123,
            "radio123": "选项A"
        }
        client = TduckClient()
        assert client.validate_webhook_payload(payload) is True


class TestMakeRequest:
    """测试内部请求方法"""

    @patch("requests.get")
    def test_request_adds_api_key(self, mock_get):
        """测试请求自动添加 API Key"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 200}
        mock_get.return_value = mock_response

        # 使用 PropertyMock patch property
        mock_tduck = {
            "base_url": "https://x.tduckcloud.com",
            "api_key": "test_api_key",
            "timeout": 30
        }
        with patch.object(Config, 'tduck', new_callable=PropertyMock, return_value=mock_tduck):
            client = TduckClient()
            client._make_request("/test-endpoint")

            # 验证 API Key 被添加到参数
            call_args = mock_get.call_args
            assert "apiKey" in call_args[1]["params"]
            assert call_args[1]["params"]["apiKey"] == "test_api_key"

    @patch("requests.get")
    def test_request_with_custom_params(self, mock_get):
        """测试自定义参数"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 200}
        mock_get.return_value = mock_response

        mock_tduck = {
            "base_url": "https://x.tduckcloud.com",
            "api_key": "test_api_key",
            "timeout": 30
        }
        with patch.object(Config, 'tduck', new_callable=PropertyMock, return_value=mock_tduck):
            client = TduckClient()
            client._make_request("/test", params={"page": 1})

            call_args = mock_get.call_args
            assert call_args[1]["params"]["page"] == 1
            assert "apiKey" in call_args[1]["params"]