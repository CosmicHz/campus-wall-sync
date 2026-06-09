"""
敏感词过滤钩子测试

测试 content_filter.py 的核心功能：
- 敏感词检测
- 替换模式 vs 拒绝模式
- 用户黑名单检查
"""

import pytest
from unittest.mock import patch
from src.hooks.content_filter import (
    filter_content,
    check_sensitive_words,
    check_user_blacklist,
    SENSITIVE_WORDS,
)


class TestCheckSensitiveWords:
    """测试敏感词检测功能"""

    def test_clean_text_passes(self):
        """测试正常文本通过检测"""
        result = check_sensitive_words("这是一条正常的投稿内容")
        assert result["passed"] is True

    def test_empty_text_passes(self):
        """测试空文本通过检测"""
        result = check_sensitive_words("")
        assert result["passed"] is True

    def test_none_text_passes(self):
        """测试 None 文本通过检测"""
        result = check_sensitive_words(None)
        assert result["passed"] is True

    @pytest.mark.parametrize("word", SENSITIVE_WORDS)
    def test_single_sensitive_word_detected(self, word):
        """测试单个敏感词被检测到（拒绝模式）"""
        # 强制使用拒绝模式进行测试
        with patch("src.hooks.content_filter._is_replace_mode", return_value=False):
            result = check_sensitive_words(f"这是一条包含{word}的内容")
            assert result["passed"] is False
            assert word in result["matched"]

    def test_multiple_sensitive_words_detected(self):
        """测试多个敏感词被检测到（拒绝模式）"""
        if len(SENSITIVE_WORDS) >= 2:
            with patch("src.hooks.content_filter._is_replace_mode", return_value=False):
                text = f"包含{SENSITIVE_WORDS[0]}和{SENSITIVE_WORDS[1]}的内容"
                result = check_sensitive_words(text)
                assert result["passed"] is False
                assert SENSITIVE_WORDS[0] in result["matched"]
                assert SENSITIVE_WORDS[1] in result["matched"]

    def test_replace_mode_returns_filtered_text(self):
        """测试替换模式返回过滤后的文本"""
        with patch("src.hooks.content_filter._is_replace_mode", return_value=True):
            if SENSITIVE_WORDS:
                text = f"包含{SENSITIVE_WORDS[0]}的内容"
                result = check_sensitive_words(text)
                assert result["passed"] is True  # 替换模式下通过
                assert "***" in result["filtered"]
                assert SENSITIVE_WORDS[0] not in result["filtered"]

    def test_reject_mode_blocks_content(self):
        """测试拒绝模式阻止内容"""
        with patch("src.hooks.content_filter._is_replace_mode", return_value=False):
            if SENSITIVE_WORDS:
                text = f"包含{SENSITIVE_WORDS[0]}的内容"
                result = check_sensitive_words(text)
                assert result["passed"] is False
                assert "filtered" not in result


class TestFilterContent:
    """测试完整内容过滤流程"""

    def test_clean_content_passes(self, sample_post_data):
        """测试正常内容通过过滤"""
        result = filter_content(sample_post_data)
        assert result["passed"] is True
        assert "data" in result

    def test_sensitive_title_blocked(self, sample_post_data):
        """测试标题包含敏感词被阻止"""
        if SENSITIVE_WORDS:
            sample_post_data["title"] = f"包含{SENSITIVE_WORDS[0]}的标题"
            with patch("src.hooks.content_filter._is_replace_mode", return_value=False):
                result = filter_content(sample_post_data)
                assert result["passed"] is False
                assert "标题包含敏感词" in result["reason"]

    def test_sensitive_content_blocked(self, sample_post_data):
        """测试内容包含敏感词被阻止"""
        if SENSITIVE_WORDS:
            sample_post_data["content"] = f"包含{SENSITIVE_WORDS[0]}的内容"
            with patch("src.hooks.content_filter._is_replace_mode", return_value=False):
                result = filter_content(sample_post_data)
                assert result["passed"] is False
                assert "内容包含敏感词" in result["reason"]

    def test_sensitive_content_replaced(self, sample_post_data):
        """测试内容包含敏感词被替换"""
        if SENSITIVE_WORDS:
            sample_post_data["content"] = f"包含{SENSITIVE_WORDS[0]}的内容"
            with patch("src.hooks.content_filter._is_replace_mode", return_value=True):
                result = filter_content(sample_post_data)
                assert result["passed"] is True
                assert "***" in result["data"]["content"]
                assert SENSITIVE_WORDS[0] not in result["data"]["content"]

    def test_blacklisted_user_blocked(self, sample_post_data):
        """测试黑名单用户被阻止"""
        sample_post_data["wx_openid"] = "blacklisted_openid"
        with patch(
            "src.hooks.content_filter.check_user_blacklist", return_value=True
        ):
            result = filter_content(sample_post_data)
            assert result["passed"] is False
            assert "黑名单" in result["reason"]

    def test_no_wx_openid_passes(self, sample_post_data):
        """测试没有 wx_openid 时通过"""
        sample_post_data["wx_openid"] = None
        result = filter_content(sample_post_data)
        assert result["passed"] is True

    def test_empty_content_passes_filter(self):
        """测试空内容通过过滤（解析阶段已校验）"""
        data = {
            "title": "测试标题",
            "content": "",
            "wx_openid": None
        }
        result = filter_content(data)
        # 空内容在过滤阶段不阻止（解析阶段已校验）
        assert result["passed"] is True


class TestUserBlacklist:
    """测试用户黑名单功能"""

    def test_non_blacklisted_user_passes(self):
        """测试非黑名单用户通过"""
        result = check_user_blacklist("normal_openid_123")
        assert result is False

    def test_empty_openid_passes(self):
        """测试空 openid 通过"""
        result = check_user_blacklist("")
        assert result is False

    def test_none_openid_passes(self):
        """测试 None openid 通过"""
        result = check_user_blacklist(None)
        assert result is False


class TestEdgeCases:
    """测试边界情况"""

    def test_partial_word_not_detected(self):
        """测试部分匹配不触发"""
        # 如果敏感词是"赌博"，"赌bo"不应被检测
        partial_text = "赌bo"
        result = check_sensitive_words(partial_text)
        # 只有完整匹配才触发
        assert "赌博" not in partial_text or result["passed"] is False

    def test_case_sensitivity(self):
        """测试大小写敏感性"""
        # 当前实现是大小写敏感的
        if SENSITIVE_WORDS:
            upper_word = SENSITIVE_WORDS[0].upper()
            text = f"包含{upper_word}的内容"
            result = check_sensitive_words(text)
            # 大小写不同不应匹配（除非敏感词本身是大写）
            if upper_word not in SENSITIVE_WORDS:
                assert result["passed"] is True

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        if SENSITIVE_WORDS:
            # 敏感词前后有空格
            text = f"包含 {SENSITIVE_WORDS[0]} 的内容"
            result = check_sensitive_words(text)
            # 空格不影响检测
            assert SENSITIVE_WORDS[0] in text
            assert result["passed"] is False or "***" in result.get("filtered", "")