"""
配置管理模块

负责从 config.json 读取所有配置信息，将密钥和敏感配置与代码分离。
开发组只需要修改 config.json，不需要碰代码。

配置文件结构说明：
- app: Flask 应用配置
- database: SQLite 数据库配置
- halo: Halo 博客 API 配置
- tduck: tduck 表单平台配置
- review: 审核配置（人工/AI）

支持热更新（无需重启服务）：
- 调用 Config.reload() 方法重新加载配置
- 通过 API 接口 POST /api/config/reload 触发热更新
- 支持热更新的配置项：tduck.api_key, halo.api_token, tduck.field_ids, review.*, content_filter.*
- 不支持热更新（需重启）：database.path, app.host, app.port

使用方法：
    # 修改 config.json 后调用热更新
    curl -X POST http://localhost:5000/api/config/reload
    
    # 或在代码中调用
    from src.config import config
    config.reload()
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class Config:
    """
    配置类，单例模式，全局唯一配置实例
    
    支持热更新：
    - reload(): 重新加载配置文件
    - get_config_path(): 获取当前配置文件路径
    """

    _instance: Optional["Config"] = None
    _config_data: Dict[str, Any] = {}
    _config_path: Optional[Path] = None  # 记录配置文件路径

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """
        加载配置文件

        查找顺序：
        1. 环境变量 CONFIG_PATH 指定的路径
        2. 当前目录的 config.json
        3. 上级目录的 config.json
        4. src 目录上级的 config.json
        """
        config_paths = [
            Path("config.json"),
            Path("../config.json"),
            Path(__file__).parent.parent / "config.json",
        ]

        # 检查环境变量
        env_config_path = os.environ.get("CONFIG_PATH")
        if env_config_path:
            config_paths.insert(0, Path(env_config_path))

        for config_path in config_paths:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
                self._config_path = config_path  # 记录路径
                logger.info(f"[配置] 已加载配置文件: {config_path}")
                return

        raise FileNotFoundError(
            "未找到配置文件！请复制 config.json.example 为 config.json 并填写配置"
        )

    def reload(self) -> bool:
        """
        热更新：重新加载配置文件
        
        Returns:
            是否成功重载
        """
        try:
            if self._config_path and self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
                logger.info(f"[配置] 热更新成功: {self._config_path}")
                return True
            else:
                # 如果没有记录路径，尝试重新查找
                self._load_config()
                return True
        except Exception as e:
            logger.error(f"[配置] 热更新失败: {e}")
            return False

    def get_config_path(self) -> Optional[str]:
        """
        获取当前配置文件路径
        
        Returns:
            配置文件路径字符串
        """
        return str(self._config_path) if self._config_path else None

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        Args:
            key: 配置键，支持点号分隔的嵌套键，如 "halo.api_url"
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    @property
    def app(self) -> Dict[str, Any]:
        """获取应用配置"""
        return self._config_data.get("app", {})

    @property
    def halo(self) -> Dict[str, Any]:
        """获取Halo博客配置"""
        return self._config_data.get("halo", {})

    @property
    def questionnaire(self) -> Dict[str, Any]:
        """获取问卷星配置"""
        return self._config_data.get("questionnaire", {})

    @property
    def review(self) -> Dict[str, Any]:
        """获取审核配置"""
        return self._config_data.get("review", {})

    @property
    def database(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self._config_data.get("database", {})

    @property
    def tduck(self) -> Dict[str, Any]:
        """获取 tduck 配置"""
        return self._config_data.get("tduck", {})

    @property
    def content_filter(self) -> Dict[str, Any]:
        """获取内容过滤配置"""
        return self._config_data.get("content_filter", {})

    @classmethod
    def reset(cls):
        """重置配置实例（用于测试）"""
        cls._instance = None
        cls._config_path = None


config = Config()
