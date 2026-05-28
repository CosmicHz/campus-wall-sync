"""
数据模型定义

定义投稿数据的存储结构。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from src.database import Base


class Post(Base):
    """
    投稿数据模型

    存储从 tduck 接收并审核通过的投稿。

    状态流转：
    - pending: 待同步到 Halo
    - synced: 已同步到 Halo
    - rejected: 已拒绝（不再同步）

    其它字段说明：
    - title: 投稿标题（由班级+姓名自动生成）
    - content: 投稿内容（用户输入的原始内容）
    - tags: 标签列表（如班级名称）
    - class_name: 班级（原始值）
    - user_name: 真实姓名（原始值）
    - wx_nickname: 微信昵称（原始值）
    - wx_openid: 微信 openid（原始值，带索引）
    - wx_avatar: 微信头像 URL（原始值）
    - submit_address: 提交地点
    - submit_time: tduck 提交时间
    - status: 状态（pending/synced/rejected）
    - tduck_id: tduck 记录 ID
    - tduck_serial: tduck 投稿序号
    - halo_post_id: Halo 文章 ID（同步后）
    - halo_post_url: Halo 文章链接（同步后）
    - created_at: 创建时间
    - synced_at: 同步到 Halo 的时间

    动态计算属性：
    - author: 作者名称（优先级：微信昵称 > 真实姓名 > "匿名"）

    方法：
    - to_dict(): 转换为字典，用于 API 返回
    - to_markdown(): 转换为 Markdown 格式，用于同步到 Halo
    """
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    title = Column(String(255), nullable=False, comment="投稿标题")
    content = Column(Text, nullable=False, comment="投稿内容（用户输入的原始内容）")
    tags = Column(JSON, default=list, comment="标签列表")

    class_name = Column(String(50), comment="班级")
    user_name = Column(String(50), comment="姓名（真实姓名）")
    wx_nickname = Column(String(100), comment="微信昵称")
    wx_openid = Column(String(100), index=True, comment="微信 openid")
    wx_avatar = Column(String(255), comment="微信头像 URL")
    submit_address = Column(String(100), comment="提交地点")
    submit_time = Column(String(50), comment="tduck 提交时间")

    status = Column(
        String(20),
        default="pending",
        index=True,
        comment="状态: pending/synced/rejected"
    )

    tduck_id = Column(Integer, comment="tduck 记录 ID")
    tduck_serial = Column(Integer, comment="tduck 投稿序号")

    halo_post_id = Column(String(50), comment="Halo 文章 ID（同步后）")
    halo_post_url = Column(String(255), comment="Halo 文章链接（同步后）")

    raw_data = Column(JSON, comment="tduck 原始数据（JSON 格式，用于数据还原）")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    synced_at = Column(DateTime, comment="同步到 Halo 的时间")

    @property
    def author(self) -> str:
        """
        动态计算作者名称

        优先级：微信昵称 > 真实姓名 > "匿名"
        """
        if self.wx_nickname:
            return self.wx_nickname
        if self.user_name:
            return self.user_name
        return "匿名"

    def __repr__(self):
        return f"<Post(id={self.id}, title='{self.title}', status='{self.status}')>"

    def to_dict(self):
        """
        转换为字典

        用于 API 返回 JSON 数据。
        """
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "tags": self.tags or [],
            "class_name": self.class_name,
            "user_name": self.user_name,
            "wx_nickname": self.wx_nickname,
            "wx_openid": self.wx_openid,
            "wx_avatar": self.wx_avatar,
            "submit_address": self.submit_address,
            "submit_time": self.submit_time,
            "status": self.status,
            "tduck_id": self.tduck_id,
            "tduck_serial": self.tduck_serial,
            "halo_post_id": self.halo_post_id,
            "halo_post_url": self.halo_post_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }

    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式

        用于同步到 Halo 博客时生成格式化内容。
        """
        meta = (
            f"**作者**：{self.author}\n"
            f"**班级**：{self.class_name or '未填写'}\n"
            f"**姓名**：{self.user_name or '未填写'}\n"
        )

        footer = (
            f"> 投稿序号：{self.tduck_serial or 'N/A'}\n"
            f"> 提交时间：{self.submit_time or '未知'}\n"
            f"> 提交地点：{self.submit_address or '未知'}\n"
            f"> 来源：tduck 表单投稿\n"
        )

        return f"{meta}\n\n---\n\n{self.content}\n\n---\n\n{footer}"
