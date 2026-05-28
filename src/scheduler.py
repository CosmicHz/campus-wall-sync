"""
定时同步模块

定期从 tduck API 获取数据并同步到数据库。
用于替代 Webhook 推送方式。
"""

import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def sync_tduck_data():
    """
    从 tduck API 同步数据到数据库

    这个函数会被定时调用，获取最新的表单数据并存入数据库。
    """
    from src.config import config
    from src.database import get_session
    from src.models import Post
    from src.services.tduck_client import TduckClient
    from src.hooks.questionnaire_parser import parse_questionnaire
    from src.hooks.content_filter import filter_content

    tduck_config = config.tduck
    if not tduck_config.get("enabled", True):
        logger.debug("tduck 同步已禁用，跳过")
        return

    logger.info("开始定时同步 tduck 数据...")

    try:
        tduck_client = TduckClient()
        
        sync_config = tduck_config.get("sync", {})
        last_sync_time = sync_config.get("last_sync_time")
        
        records = tduck_client.get_all_form_data()
        
        if not records:
            logger.info("没有获取到新数据")
            return

        session = get_session()
        success_count = 0
        skip_count = 0
        error_count = 0

        for record in records:
            try:
                tduck_id = record.get("id")
                
                existing = session.query(Post).filter(Post.tduck_id == tduck_id).first()
                if existing:
                    skip_count += 1
                    continue

                parsed_data = parse_questionnaire(record)

                filtered_result = filter_content(parsed_data)
                if not filtered_result["passed"]:
                    logger.warning(f"记录 {tduck_id} 未通过敏感词过滤，跳过")
                    skip_count += 1
                    continue

                filtered_data = filtered_result["data"]

                post = Post(
                    title=filtered_data["title"],
                    content=filtered_data["content"],
                    class_name=filtered_data.get("class_name"),
                    user_name=filtered_data.get("user_name"),
                    wx_nickname=filtered_data.get("wx_nickname"),
                    wx_openid=filtered_data.get("wx_openid"),
                    wx_avatar=filtered_data.get("wx_avatar"),
                    submit_address=filtered_data.get("submit_address"),
                    submit_time=filtered_data.get("submit_time"),
                    tags=filtered_data.get("tags", []),
                    status="pending",
                    tduck_id=tduck_id,
                    tduck_serial=filtered_data.get("tduck_serial"),
                    raw_data=filtered_data.get("raw_data"),
                )
                session.add(post)
                session.commit()

                success_count += 1
                logger.debug(f"同步记录 {tduck_id}: {filtered_data['title']}")

            except ValueError as e:
                logger.warning(f"跳过无效记录 {record.get('id')}: {e}")
                skip_count += 1

            except Exception as e:
                logger.error(f"同步记录 {record.get('id')} 失败: {e}")
                error_count += 1

        logger.info(f"定时同步完成 - 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}")

    except Exception as e:
        logger.error(f"定时同步失败: {e}", exc_info=True)


def start_scheduler(interval_minutes: int = 5):
    """
    启动定时任务调度器

    Args:
        interval_minutes: 同步间隔（分钟），默认 5 分钟
    """
    from src.config import config

    sync_config = config.tduck.get("sync", {})
    interval = sync_config.get("interval_minutes", interval_minutes)

    if not sync_config.get("enabled", True):
        logger.info("定时同步已禁用")
        return

    scheduler.add_job(
        sync_tduck_data,
        trigger=IntervalTrigger(minutes=interval),
        id="sync_tduck_data",
        name="同步 tduck 数据",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(f"定时同步已启动，间隔: {interval} 分钟")


def stop_scheduler():
    """停止定时任务调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("定时同步已停止")


def get_scheduler_status() -> dict:
    """
    获取调度器状态

    Returns:
        调度器状态信息
    """
    jobs = scheduler.get_jobs()
    
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }
