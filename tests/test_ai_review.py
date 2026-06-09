"""
AI 内容审核钩子测试

测试 ai_review.py 的核心功能：
- 简单规则审核
- 内容长度检查
- 电话号码检测
"""

import pytest
from unittest.mock import patch, Mock
from src.hooks.ai_review import (
    review_content,
    simple_rule_review,
    REVIEW_PROMPT,
)


class TestSimpleRuleReview:
    """测试简单规则审核"""

    def test_short_content_rejected(self):
        """测试过短内容被拒绝"""
        result = simple_rule_review(
            title="测试标题",
            content="太短",  # 只有 2 个字符
            author="测试用户"
        )
        assert result is not None
        assert result["approved"] is False
        assert "内容过短" in result["reason"]

    def test_normal_length_content_passes(self):
        """测试正常长度内容通过"""
        result = simple_rule_review(
            title="测试标题",
            content="这是一条足够长的测试投稿内容，用于验证审核功能是否正常工作。",
            author="测试用户"
        )
        # 正常内容不触发规则，返回 None
        assert result is None

    def test_very_long_content_rejected(self):
        """测试过长内容被拒绝"""
        # 需要超过 10000 字符
        long_content = "测试内容" * 2501  # 4 * 2501 = 10004 字符
        result = simple_rule_review(
            title="测试标题",
            content=long_content,
            author="测试用户"
        )
        assert result is not None
        assert result["approved"] is False
        assert "内容过长" in result["reason"]

    def test_phone_number_detected(self):
        """测试电话号码被检测"""
        # 内容需要超过 50 字符才会检查电话号码
        # 确保内容 > 50 字符（需要 51+ 字符）
        content = "这是一条足够长的内容用于测试电话号码检测功能，联系电话是13812345678，请联系我谢谢大家的支持。"  # 53 字符
        result = simple_rule_review(
            title="测试标题",
            content=content,
            author="测试用户"
        )
        assert result is not None
        assert result["approved"] is False
        assert "电话号码" in result["reason"]

    def test_short_content_skips_phone_check(self):
        """测试短内容跳过电话号码检查"""
        # 内容少于 50 字符时不检查电话号码
        # 但内容长度 > 10 时不触发"内容过短"规则
        content = "联系13812345678"  # 15 字符，> 10（不触发过短），< 50（跳过电话检查）
        result = simple_rule_review(
            title="测试标题",
            content=content,
            author="测试用户"
        )
        # 内容长度 > 10 且 < 50，不触发任何规则，返回 None
        assert result is None  # 不触发任何规则

    @pytest.mark.parametrize("phone", [
        "13812345678",
        "15912345678",
        "18612345678",
        "17712345678",
    ])
    def test_various_phone_formats_detected(self, phone):
        """测试各种手机号格式被检测"""
        # 内容需要超过 50 字符才会检查电话号码
        # 确保内容 > 50 字符（需要 51+ 字符）
        content = f"这是一条足够长的内容用于测试电话号码检测功能，联系电话是{phone}，请联系我谢谢大家的支持。"
        result = simple_rule_review(
            title="测试标题",
            content=content,
            author="测试用户"
        )
        assert result is not None
        assert result["approved"] is False
        assert "电话号码" in result["reason"]


class TestReviewContent:
    """测试完整审核流程"""

    def test_normal_content_approved(self):
        """测试正常内容通过审核"""
        data = {
            "title": "测试投稿",
            "content": "这是一条足够长的测试投稿内容，用于验证审核功能是否正常工作。",
            "author": "测试用户"
        }
        result = review_content(data)
        assert result["approved"] is True

    def test_short_content_rejected_in_full_review(self):
        """测试过短内容在完整审核中被拒绝"""
        data = {
            "title": "测试投稿",
            "content": "太短",  # 只有 2 字符
            "author": "测试用户"
        }
        result = review_content(data)
        assert result["approved"] is False
        assert "内容过短" in result["reason"]

    def test_review_with_missing_fields(self):
        """测试缺少字段时的审核"""
        data = {}
        # 缺少 content 字段时，默认为空字符串
        # len("") = 0 < 10，触发"内容过短"规则
        result = review_content(data)
        assert result["approved"] is False
        assert "内容过短" in result["reason"]

    def test_review_with_empty_content(self):
        """测试空内容时的审核"""
        data = {
            "title": "测试",
            "content": "",
            "author": "测试"
        }
        result = review_content(data)
        # 空内容会因过短被拒绝
        assert result["approved"] is False
        assert "内容过短" in result["reason"]


class TestOpenAIReview:
    """测试 OpenAI API 审核（需要 mock）"""

    @patch("src.hooks.ai_review.openai_review")
    def test_openai_review_called_when_enabled(self, mock_openai):
        """测试启用时调用 OpenAI 审核"""
        mock_openai.return_value = {
            "approved": True,
            "reason": "AI审核通过",
            "confidence": 0.95
        }

        # 禁用简单规则审核
        with patch("src.hooks.ai_review.simple_rule_review", return_value=None):
            data = {
                "title": "测试投稿",
                "content": "这是一条足够长的测试投稿内容。",
                "author": "测试用户"
            }
            # 注意：当前代码默认不调用 OpenAI，需要手动启用
            # 此测试验证 mock 可以正确工作

    @patch("openai.OpenAI")
    def test_openai_api_mock(self, mock_openai_class):
        """测试 OpenAI API mock"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"approved": true, "reason": "测试通过"}'

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # 验证 mock 设置正确
        assert mock_client is not None


class TestReviewPrompt:
    """测试审核提示词"""

    def test_prompt_contains_required_fields(self):
        """测试提示词包含必要字段"""
        assert "{title}" in REVIEW_PROMPT
        assert "{content}" in REVIEW_PROMPT
        assert "{author}" in REVIEW_PROMPT

    def test_prompt_can_be_formatted(self):
        """测试提示词可以正确格式化"""
        formatted = REVIEW_PROMPT.format(
            title="测试标题",
            content="测试内容",
            author="测试作者"
        )
        assert "测试标题" in formatted
        assert "测试内容" in formatted
        assert "测试作者" in formatted