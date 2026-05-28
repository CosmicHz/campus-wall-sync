"""
问卷数据解析钩子

这个程序负责将 tduck 表单提交的原始数据转换为标准格式。
当表单的题目或选项有变化时，只需要修改这个文件。

标准输出格式：
{
    "title": "投稿标题",
    "content": "投稿内容（用户输入的原始内容）",
    "class_name": "班级",
    "user_name": "姓名",
    "wx_nickname": "微信昵称",
    "wx_openid": "微信openid",
    "submit_address": "提交地点",
    "submit_time": "提交时间",
    "tags": ["标签1", "标签2"],
    "tduck_id": 123,
    "tduck_serial": 4
}

tduck Webhook 数据示例：
{
    "input1773416359370": "高一十三班",
    "input1773416363353": "小明",
    "textarea1773416364971": "我喜欢小红",
    "serialNumber": 4,
    "wxUserInfo": {
        "nickname": "xiaoming",
        "openid": "xxx"
    },
    "createTime": "2026-03-14 00:14:05",
    "eventType": "form_data_add"
    ...
}
"""

from typing import Dict, Any, List
import logging
from src.config import config

logger = logging.getLogger(__name__)


def _safe_str(value: Any) -> str | None:
    """
    安全地将值转换为字符串，处理各种异常情况
    
    Args:
        value: 任意类型的值
        
    Returns:
        处理后的字符串，如果为空则返回 None
    """
    if value is None:
        return None
    try:
        result = str(value).strip()
        return result if result else None
    except Exception:
        return None


# ========================================
# tduck 字段映射配置
# ========================================

# 从配置文件读取字段 ID（优先），如果没有配置则使用默认值
tduck_field_ids = config.tduck.get("field_ids", {})
FIELD_CLASS = tduck_field_ids.get("class", "input1773416359370")      # 班级字段 ID
FIELD_NAME = tduck_field_ids.get("name", "input1773416363353")        # 姓名字段 ID
FIELD_CONTENT = tduck_field_ids.get("content", "textarea1773416364971")  # 投稿内容字段 ID


def parse_questionnaire(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析 tduck 表单提交的原始数据

    【修改这里的代码来适配你的表单】

    tduck Webhook 数据结构 (以数据推送返回结构为例)：
    {
        // 表单字段（直接在顶层）
        "input1773416359370": "高一十三班",
        "input1773416363353": "小明",
        "textarea1773416364971": "投稿内容",
        
        // 元数据
        "serialNumber": 4,
        "dataId": "xxx",
        "formKey": "88888888",
        
        // 用户信息
        "wxUserInfo": {
            "nickname": "xiaoming",
            "openid": "xxx"
        },
        
        // 提交信息
        "submitAddress": "广东省-广州市",
        "createTime": "2026-03-14 00:14:05",
        "beginTime": "2026-03-14 00:13:19",
        
        // 事件类型
        "eventType": "form_data_add",
        "eventTime": 1773498073370
    }

    Args:
        raw_data: tduck Webhook 发送的原始数据

    Returns:
        结构化的解析结果（原始数据）

    Raises:
        ValueError: 必要字段缺失
    """
    logger.info("开始解析 tduck 表单数据...")

    # ========================================
    # 数据提取
    # ========================================

    # tduck Webhook 数据是扁平结构，字段直接在顶层
    # 但为了兼容 API 数据（有 originalData 嵌套），做以下处理
    form_data = raw_data
    
    # 如果存在 originalData，优先使用（API 数据格式）
    if "originalData" in raw_data and isinstance(raw_data["originalData"], dict):
        form_data = raw_data["originalData"]
        logger.debug("识别为 API 数据，使用 originalData 嵌套结构")

    # 提取投稿内容（必须）
    content = form_data.get(FIELD_CONTENT, "").strip()
    if not content:
        # 调试信息：打印所有可用字段
        available_fields = list(form_data.keys())
        logger.error(f"字段 '{FIELD_CONTENT}' 未找到！可用字段：{available_fields}")
        raise ValueError(f"投稿内容不能为空（字段 ID: {FIELD_CONTENT}，可用字段：{', '.join(available_fields)}...)")

    # 提取班级和姓名
    class_name = form_data.get(FIELD_CLASS, "").strip() or None
    user_name = form_data.get(FIELD_NAME, "").strip() or None

    # 提取微信用户信息（安全处理，字段可能不存在或格式异常）
    # 这种设计可能并非必须，所以此处以注释的方式保留简洁版代码
    # wx_info = raw_data.get("wxUserInfo", {})
    # wx_nickname = wx_info.get("nickname", "").strip() or None
    # wx_openid = wx_info.get("openid", "").strip() or None
    # wx_avatar = wx_info.get("headImgUrl", "").strip() or None
    try:
        wx_info = raw_data.get("wxUserInfo", {}) or {}
        if not isinstance(wx_info, dict):
            logger.warning(f"wxUserInfo 格式异常: {type(wx_info)}，已忽略")
            wx_info = {}
        
        wx_nickname = _safe_str(wx_info.get("nickname"))
        wx_openid = _safe_str(wx_info.get("openid"))
        wx_avatar = _safe_str(wx_info.get("headImgUrl"))
    except Exception as e:
        logger.warning(f"解析微信用户信息失败: {e}，已忽略")
        wx_nickname = None
        wx_openid = None
        wx_avatar = None

    # 如果 wxUserInfo 中没有 openid，尝试从顶层获取
    if not wx_openid:
        wx_openid = _safe_str(raw_data.get("wxOpenId"))

    # 提取提交信息（安全处理）
    submit_address = _safe_str(raw_data.get("submitAddress"))
    submit_time = _safe_str(raw_data.get("createTime"))

    # 构建标题
    if class_name and user_name:
        title = f"{class_name}-{user_name}的投稿"
    elif user_name:
        title = f"{user_name}的投稿"
    elif class_name:
        title = f"{class_name}的投稿"
    else:
        serial = raw_data.get("serialNumber", "")
        title = f"投稿-{serial or submit_time or '未知'}"

    # 提取标签（可选，可以根据班级自动分类）
    tags = []
    if class_name:
        tags.append(class_name)

    # ========================================
    # 返回结构化数据
    # ========================================

    result = {
        "title": title,
        "content": content,
        "class_name": class_name,
        "user_name": user_name,
        "wx_nickname": wx_nickname,
        "wx_openid": wx_openid,
        "wx_avatar": wx_avatar,
        "submit_address": submit_address,
        "submit_time": submit_time,
        "tags": tags,
        "tduck_id": raw_data.get("id"),
        "tduck_serial": raw_data.get("serialNumber"),
        "raw_data": raw_data,
    }

    logger.info(f"解析完成 - 标题: {title}")
    return result


def parse_from_api_response(api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 tduck 全量数据同步 API 解析多条记录

    用于批量同步历史数据，API 格式：
    https://x.tduckcloud.com/tduck-api/sync/form/data?apiKey=xxx

    Args:
        api_data: API 返回的 JSON 数据

    Returns:
        标准格式的解析结果列表
    """
    logger.info("从 tduck API 解析数据...")

    records = []
    data_list = api_data.get("data", {}).get("records", [])

    for record in data_list:
        try:
            parsed = parse_questionnaire(record)
            records.append(parsed)
        except ValueError as e:
            logger.warning(f"跳过无效记录 {record.get('id')}: {e}")
            continue

    logger.info(f"成功解析 {len(records)} 条记录")
    return records


# ========================================
# 调试/测试用
# ========================================

if __name__ == "__main__":
    # 使用模拟 Webhook 数据测试
    mock_webhook_data = {
        "input1773416359370": "高一十三班",
        "input1773416363353": "小明",
        "textarea1773416364971": "我喜欢小红",
        "dataId": "22c4555557cb4ad9a0000000000042b3",
        "formKey": "88888888",
        "serialNumber": 4,
        "submitUa": {
            "os": {"name": "Android", "version": "15"},
            "ua": "Mozilla/5.0 (Linux; Android 15; NX733J Build/AQ3A.240812.002; wv)...",
        },
        "submitOs": "Android",
        "submitBrowser": "WeChat",
        "submitRequestIp": "111.111.0.111",
        "submitAddress": "广东省-广州市",
        "completeTime": 45527,
        "wxOpenId": "oH28888888l8-EUZ77777777nMvY",
        "wxUserInfo": {
            "sex": 0,
            "city": "",
            "openid": "oH28888888l8-EUZ77777777nMvY",
            "country": "",
            "unionId": "oMovy0_0h86666666666YZvomSIA",
            "nickname": "xiaoming",
            "province": "",
            "headImgUrl": "https://thirdwx.qlogo.cn/mmopen/vi_32/...",
            "privileges": [],
            "snapshotUser": None
        },
        "extValue": "",
        "userId": None,
        "createByName": None,
        "updateByName": None,
        "otherParam": {},
        "beginTime": "2026-03-14 00:13:19",
        "deleted": False,
        "createBy": "",
        "updateBy": None,
        "id": 623899,
        "createTime": "2026-03-14 00:14:05",
        "updateTime": "2026-03-14 00:14:05",
        "eventType": "form_data_add",
        "eventTime": 1773498073370
    }

    print("=" * 60)
    print("使用模拟 Webhook 数据测试")
    print("=" * 60)
    
    result = parse_questionnaire(mock_webhook_data)
    print("\n解析结果:")
    print(f"  标题: {result['title']}")
    print(f"  内容: {result['content']}")
    print(f"  班级: {result['class_name']}")
    print(f"  姓名: {result['user_name']}")
    print(f"  微信昵称: {result['wx_nickname']}")
    print(f"  微信openid: {result['wx_openid']}")
    print(f"  提交地点: {result['submit_address']}")
    print(f"  提交时间: {result['submit_time']}")
    print(f"  标签: {result['tags']}")
