"""
Halo博客API客户端

封装与Halo博客系统的交互，包括：
- 测试连接
- 创建文章
- 更新文章
- 发布文章
- 删除文章

Halo 版本: 2.22.14
API 文档参考: https://blog.mochencloud.cn:1443/archives/halo-api-complete-guide-9cd78d
Halo API 在线文档: https://api.halo.run
"""

import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.config import config


class HaloClient:
    """
    Halo博客API客户端

    使用Halo 2.22.14的REST API进行文章管理。
    配置信息从 config.json 的 halo 部分读取。

    Halo 2.22.14 API 格式：
    - 端点: /apis/uc.api.content.halo.run/v1alpha1/posts
    - 认证: Authorization: Bearer {pat_token} 或 Basic Auth
    - 发布流程: 创建文章 -> 更新草稿 -> 发布
    """

    def __init__(self):
        """从配置初始化Halo客户端"""
        halo_config = config.halo

        self.api_url = halo_config.get("api_url", "").rstrip("/")
        self.api_token = halo_config.get("api_token", "")
        self.site_name = halo_config.get("site_name", "default")
        self.timeout = halo_config.get("timeout", 30)
        self.default_category = halo_config.get("default_category", "表白墙")
        self.default_tags = halo_config.get("default_tags", ["投稿", "校园墙"])
        self.owner = halo_config.get("owner", "admin")

        self.logger = logging.getLogger(__name__)

    def _get_headers(self) -> Dict[str, str]:
        """动态构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送HTTP请求到Halo API

        Args:
            method: HTTP方法 (GET, POST, PUT, DELETE)
            endpoint: API端点路径
            data: 请求体数据
            params: URL查询参数

        Returns:
            JSON响应数据

        Raises:
            requests.RequestException: 请求失败时抛出异常
        """
        url = f"{self.api_url}{endpoint}"
        self.logger.debug(f"请求 Halo API: {method} {url}")
        if data:
            self.logger.debug(f"请求体: {json.dumps(data, ensure_ascii=False)[:500]}")

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            self.logger.debug(f"响应状态码: {response.status_code}")
            
            if response.status_code != 204 and response.text:
                try:
                    result = response.json()
                    self.logger.debug(f"响应数据: {json.dumps(result, ensure_ascii=False)[:500]}")
                    return result
                except:
                    return {"status_code": response.status_code, "text": response.text}
            
            return {"status_code": response.status_code}

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Halo API请求失败: {str(e)}", exc_info=True)
            raise

    def test_connection(self) -> Dict[str, Any]:
        """
        测试Halo博客连接

        Returns:
            连接状态信息
        """
        try:
            result = self._make_request(
                "GET", 
                "/apis/uc.api.content.halo.run/v1alpha1/posts", 
                params={"page": 0, "size": 1}
            )
            return {
                "status": "connected",
                "site_name": self.site_name,
                "api_url": self.api_url,
                "message": "Halo API 连接成功"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    def create_post(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        publish: bool = True
    ) -> Dict[str, Any]:
        """
        创建新文章并发布

        Halo 2.22.14 API 工作流程：
        1. POST /apis/uc.api.content.halo.run/v1alpha1/posts 创建文章（草稿）
        2. PUT /posts/{name}/draft 更新草稿内容
        3. PUT /posts/{name}/publish 发布文章

        Args:
            title: 文章标题
            content: 文章内容（支持Markdown）
            tags: 文章标签列表
            category: 文章分类
            publish: 是否立即发布

        Returns:
            创建的文章信息，包含metadata.name

        Raises:
            requests.RequestException: 创建失败时抛出异常
        """
        import uuid
        
        post_name = str(uuid.uuid4())
        
        slug = title.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:50]
        for char in ["?", "&", "=", "#", "%", "+", " "]:
            slug = slug.replace(char, "-")
        
        if tags is None:
            tags = self.default_tags
        if category is None:
            category = self.default_category

        content_json = json.dumps({
            "content": content,
            "raw": content,
            "rawType": "markdown"
        }, ensure_ascii=False)

        post_data = {
            "apiVersion": "content.halo.run/v1alpha1",
            "kind": "Post",
            "metadata": {
                "name": post_name,
                "annotations": {
                    "content.halo.run/preferred-editor": "default",
                    "content.halo.run/content-json": content_json
                }
            },
            "spec": {
                "title": title,
                "slug": slug,
                "allowComment": True,
                "deleted": False,
                "excerpt": {"autoGenerate": True, "raw": ""},
                "htmlMetas": [],
                "owner": self.owner,
                "pinned": False,
                "priority": 0,
                "publish": False,
                "visible": "PUBLIC",
                "tags": tags,
                "categories": [category] if category else []
            }
        }

        self.logger.info(f"正在创建文章: {title}")

        result = self._make_request(
            "POST", 
            "/apis/uc.api.content.halo.run/v1alpha1/posts", 
            post_data
        )

        created_name = result.get("metadata", {}).get("name", post_name)
        self.logger.info(f"文章创建成功，name: {created_name}")

        if publish:
            self.logger.info(f"正在发布文章: {created_name}")
            try:
                publish_result = self._make_request(
                    "PUT",
                    f"/apis/uc.api.content.halo.run/v1alpha1/posts/{created_name}/publish"
                )
                self.logger.info(f"文章发布成功: {created_name}")
            except Exception as e:
                self.logger.warning(f"文章发布失败，但文章已创建: {e}")

        return result

    def update_post(
        self,
        post_name: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        publish: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        更新现有文章

        Args:
            post_name: 文章name（UUID）
            title: 新标题（可选）
            content: 新内容（可选）
            publish: 是否发布（可选）

        Returns:
            更新后的文章信息
        """
        try:
            draft = self._make_request(
                "GET", 
                f"/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}/draft",
                params={"patched": "true"}
            )
        except:
            draft = {
                "metadata": {"name": post_name, "annotations": {}},
                "spec": {}
            }

        annotations = draft.get("metadata", {}).get("annotations", {})
        spec = draft.get("spec", {})
        
        if title:
            spec["title"] = title
            slug = title.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:50]
            spec["slug"] = slug
        
        if content:
            content_json = json.dumps({
                "content": content,
                "raw": content,
                "rawType": "markdown"
            }, ensure_ascii=False)
            
            annotations["content.halo.run/content-json"] = content_json
            annotations["content.halo.run/patched-content"] = content
            annotations["content.halo.run/patched-raw"] = content

        draft["metadata"]["annotations"] = annotations
        draft["spec"] = spec

        self.logger.info(f"正在更新文章草稿，name: {post_name}")

        result = self._make_request(
            "PUT",
            f"/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}/draft",
            draft
        )

        self.logger.info(f"文章草稿更新成功，name: {post_name}")

        if publish:
            try:
                self._make_request(
                    "PUT",
                    f"/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}/publish"
                )
                self.logger.info(f"文章发布成功: {post_name}")
            except Exception as e:
                self.logger.warning(f"文章发布失败: {e}")

        return result

    def delete_post(self, post_name: str) -> bool:
        """
        删除文章（移到回收站）

        Args:
            post_name: 文章name（UUID）

        Returns:
            是否删除成功
        """
        try:
            self._make_request(
                "PUT",
                f"/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}/recycle"
            )
            self.logger.info(f"文章已移到回收站，name: {post_name}")
            return True
        except Exception as e:
            self.logger.error(f"文章删除失败: {str(e)}", exc_info=True)
            return False

    def get_post(self, post_name: str) -> Dict[str, Any]:
        """
        获取文章详情

        Args:
            post_name: 文章name（UUID）

        Returns:
            文章信息
        """
        return self._make_request(
            "GET", 
            f"/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}"
        )

    def list_posts(self, page: int = 0, size: int = 20) -> Dict[str, Any]:
        """
        获取文章列表

        Args:
            page: 页码（从0开始）
            size: 每页数量

        Returns:
            文章列表
        """
        return self._make_request(
            "GET",
            "/apis/uc.api.content.halo.run/v1alpha1/posts",
            params={"page": page, "size": size}
        )

    def list_categories(self) -> List[Dict[str, Any]]:
        """
        获取分类列表

        Returns:
            分类列表，每个分类包含 metadata.name 和 spec.displayName
        """
        result = self._make_request(
            "GET",
            "/apis/api.content.halo.run/v1alpha1/categories"
        )
        items = result.get("items", [])
        return [
            {
                "name": item.get("metadata", {}).get("name"),
                "displayName": item.get("spec", {}).get("displayName"),
                "slug": item.get("spec", {}).get("slug")
            }
            for item in items
        ]

    def list_tags(self) -> List[Dict[str, Any]]:
        """
        获取标签列表

        Returns:
            标签列表，每个标签包含 metadata.name 和 spec.displayName
        """
        result = self._make_request(
            "GET",
            "/apis/api.content.halo.run/v1alpha1/tags"
        )
        items = result.get("items", [])
        return [
            {
                "name": item.get("metadata", {}).get("name"),
                "displayName": item.get("spec", {}).get("displayName"),
                "slug": item.get("spec", {}).get("slug")
            }
            for item in items
        ]
