"""
Tduck 表单 API 客户端

封装与 tduck 表单系统的交互，包括：
- 字段同步 API: /tduck-api/sync/form/fields
- 全量数据同步 API: /tduck-api/sync/form/data
- Webhook 数据验证

支持热更新（无需重启服务）：
- 所有配置项使用 @property 动态获取
- 修改 config.json 后调用 POST /api/config/reload 即可生效
- 支持热更新的配置：api_key, base_url, timeout, field_ids

使用方法：
    # 1. 修改 config.json 中的 tduck.api_key
    nano config.json
    
    # 2. 调用热更新 API
    curl -X POST http://localhost:5000/api/config/reload
    
    # 3. 新 API Key 立即生效，无需重启服务
"""

import logging
import requests
from typing import Dict, Any, List, Optional
from src.config import config


class TduckClient:
    """
    Tduck 表单 API 客户端

    使用 tduck 的数据同步 API 进行表单数据管理。
    配置信息从 config.json 的 tduck 部分读取。
    
    支持热更新：每次请求时获取最新配置值
    """

    def __init__(self):
        """初始化 tduck 客户端（不缓存配置）"""
        self.logger = logging.getLogger(__name__)

    @property
    def base_url(self) -> str:
        """获取 base_url（每次从 config 读取）"""
        return config.tduck.get("base_url", "https://x.tduckcloud.com")

    @property
    def api_key(self) -> str:
        """获取 api_key（每次从 config 读取）"""
        return config.tduck.get("api_key", "")

    @property
    def timeout(self) -> int:
        """获取 timeout（每次从 config 读取）"""
        return config.tduck.get("timeout", 30)

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求到 tduck API

        Args:
            endpoint: API 端点路径
            params: URL 查询参数

        Returns:
            JSON 响应数据

        Raises:
            requests.RequestException: 请求失败时抛出异常
        """
        url = f"{self.base_url}{endpoint}"

        # 添加 API Key
        if params is None:
            params = {}
        params["apiKey"] = self.api_key

        self.logger.debug(f"请求 tduck API: GET {url}")

        try:
            response = requests.get(
                url=url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"请求 tduck API 失败: {e}", exc_info=True)
            raise

    def get_form_fields(self) -> List[Dict[str, Any]]:
        """
        获取表单字段定义

        API: GET /tduck-api/sync/form/fields?apiKey=xxx

        Returns:
            字段定义列表，每个字段包含 value, label, type 等属性

        Example:
            [
                {"value": "input1773416359370", "label": "班级", "type": "INPUT"},
                {"value": "input1773416363353", "label": "姓名", "type": "INPUT"},
                {"value": "textarea1773416364971", "label": "投稿内容", "type": "TEXTAREA"}
            ]
        """
        self.logger.info("获取 tduck 表单字段定义...")

        response = self._make_request("/tduck-api/sync/form/fields")

        if response.get("code") != 200:
            raise ValueError(f"获取字段失败: {response.get('msg')}")

        fields = response.get("data", {}).get("fields", [])
        self.logger.info(f"成功获取 {len(fields)} 个字段定义")
        return fields

    def get_form_data(self) -> Dict[str, Any]:
        """
        获取表单提交数据（全量）

        API: GET /tduck-api/sync/form/data?apiKey=xxx

        注意：tduck API 不支持分页参数，只能获取全量数据

        Returns:
            包含 records, total 等字段的数据字典

        Example:
            {
                "records": [...],
                "total": 100
            }
        """
        self.logger.info("获取 tduck 表单全量数据...")

        response = self._make_request("/tduck-api/sync/form/data")

        if response.get("code") != 200:
            raise ValueError(f"获取数据失败: {response.get('msg')}")

        data = response.get("data", {})
        records = data.get("records", [])
        total = data.get("total", len(records))

        self.logger.info(f"成功获取 {len(records)} 条记录")
        return data

    def get_all_form_data(self) -> List[Dict[str, Any]]:
        """
        获取所有表单数据

        Returns:
            所有记录的列表
        """
        self.logger.info("开始获取所有表单数据...")

        data = self.get_form_data()
        records = data.get("records", [])

        self.logger.info(f"共获取 {len(records)} 条记录")
        return records

    def validate_webhook_payload(self, payload: Dict[str, Any]) -> bool:
        """
        验证 Webhook 请求的数据格式

        tduck Webhook 推送的数据格式示例：
        {
            "id": 623899,
            "serialNumber": 4,
            "createTime": "2026-03-14 00:14:05",
            "originalData": {
                "input1773416359370": "...",
                "input1773416363353": "...",
                "textarea1773416364971": "..."
            },
            "wxUserInfo": {
                "nickname": "..."
            }
        }

        Args:
            payload: Webhook 请求体

        Returns:
            数据格式是否有效
        """
        # 检查必要字段
        if not isinstance(payload, dict):
            self.logger.warning("Webhook 数据格式错误: 不是字典类型")
            return False

        # 检查是否有 originalData 或直接包含字段数据
        has_original_data = "originalData" in payload and isinstance(payload["originalData"], dict)
        has_direct_data = any(key.startswith(("input", "textarea", "radio", "checkbox")) for key in payload.keys())

        if not has_original_data and not has_direct_data:
            self.logger.warning("Webhook 数据格式错误: 缺少表单数据")
            return False

        return True


# 单例实例
tduck_client = TduckClient()
