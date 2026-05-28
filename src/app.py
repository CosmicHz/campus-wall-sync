"""
Flask 主入口

校园墙同步服务的HTTP入口，处理 tduck Webhook 并存入数据库。

工作流程：
1. tduck 收到投稿 -> 触发 Webhook -> 本服务接收
2. 调用 hooks/questionnaire_parser 解析表单数据
3. 调用 hooks/content_filter 进行敏感词过滤
4. 调用 hooks/ai_review 进行AI审核（可选）
5. 审核通过 -> 存入数据库（状态为 pending）
6. 后续可通过 API 将数据库中的投稿同步到 Halo 博客
"""

import logging
from datetime import datetime
from flask import Flask, request, jsonify
from src.config import config
from src.services.tduck_client import TduckClient
from src.services.halo_client import HaloClient
from src.utils.logger import setup_logger
from src.database import init_db, get_session, close_db
from src.models import Post


def create_app() -> Flask:
    """
    Flask应用工厂函数

    创建并配置Flask应用，注册路由和钩子。
    这里只做基础设施配置，业务逻辑都在 hooks/ 目录下。
    """
    app = Flask(__name__)

    app_config = config.app
    app.config["DEBUG"] = app_config.get("debug", False)
    app.config["HOST"] = app_config.get("host", "0.0.0.0")
    app.config["PORT"] = app_config.get("port", 5000)

    setup_logger(app_config.get("log_level", "INFO"))
    logger = logging.getLogger(__name__)

    init_db()

    tduck_client = TduckClient()
    
    halo_enabled = config.halo.get("enabled", False)
    halo_client = HaloClient() if halo_enabled else None
    if not halo_enabled:
        logger.info("Halo 同步已禁用（config.json 中 halo.enabled = false）")

    @app.route("/health", methods=["GET"])
    def health_check():
        """健康检查接口，供运维监控系统调用"""
        return jsonify({"status": "ok", "service": "campus-wall-sync"})

    @app.route("/webhook/tduck", methods=["POST"])
    def handle_tduck_webhook():
        """
        tduck Webhook 处理接口

        接收 tduck 的投稿数据，依次经过：
        1. 验证 Webhook 数据格式
        2. 解析表单数据（hooks/questionnaire_parser.py）
        3. 敏感词过滤（hooks/content_filter.py）
        4. AI审核（hooks/ai_review.py，可选）
        5. 存入数据库（状态为 pending）

        tduck Webhook 配置：
        - URL: http://your-server:5000/webhook/tduck
        - Method: POST
        - Content-Type: application/json
        """
        logger.info("收到 tduck Webhook 请求")

        try:
            data = request.get_json()
            if not data:
                logger.warning("Webhook 请求体为空")
                return jsonify({"error": "请求体为空"}), 400

            if not tduck_client.validate_webhook_payload(data):
                logger.warning("Webhook 数据格式验证失败")
                return jsonify({"error": "数据格式无效"}), 400

            logger.info(f"接收到 tduck 投稿，ID: {data.get('id')}, 序号: {data.get('serialNumber')}")

            from src.hooks.questionnaire_parser import parse_questionnaire

            parsed_data = parse_questionnaire(data)
            logger.info(f"解析后的数据 - 标题: {parsed_data['title']}, 作者姓名: {parsed_data['user_name']}")

            from src.hooks.content_filter import filter_content

            filtered_result = filter_content(parsed_data)
            if not filtered_result["passed"]:
                logger.warning(f"内容未通过敏感词过滤: {filtered_result['reason']}")
                return jsonify({
                    "status": "filtered",
                    "reason": filtered_result["reason"]
                }), 200

            filtered_data = filtered_result["data"]

            review_config = config.review
            if review_config.get("enable_ai_review", False):
                from src.hooks.ai_review import review_content

                review_result = review_content(filtered_data)
                if not review_result["approved"]:
                    logger.warning(f"内容未通过AI审核: {review_result['reason']}")
                    return jsonify({
                        "status": "pending_review",
                        "reason": review_result["reason"]
                    }), 200

            session = get_session()
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
                tduck_id=filtered_data.get("tduck_id"),
                tduck_serial=filtered_data.get("tduck_serial"),
                raw_data=filtered_data.get("raw_data"),
            )
            session.add(post)
            session.commit()

            logger.info(f"投稿已存入数据库，ID: {post.id}, 作者: {post.user_name}")
            return jsonify({
                "status": "success",
                "message": "投稿已存入数据库",
                "post_id": post.id,
                "title": filtered_data["title"],
                "author": post.author
            }), 200

        except ValueError as e:
            logger.warning(f"数据验证失败: {str(e)}")
            return jsonify({"error": str(e)}), 400

        except Exception as e:
            logger.error(f"处理 Webhook 时发生错误: {str(e)}", exc_info=True)
            return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500

    @app.route("/api/posts", methods=["GET"])
    def list_posts():
        """
        获取投稿列表

        Query Parameters:
        - status: 按状态筛选 (pending/synced/rejected)
        - page: 页码，默认 1
        - size: 每页数量，默认 20
        """
        try:
            status = request.args.get("status")
            page = int(request.args.get("page", 1))
            size = int(request.args.get("size", 20))

            session = get_session()
            query = session.query(Post)

            if status:
                query = query.filter(Post.status == status)

            total = query.count()
            posts = query.order_by(Post.created_at.desc()).offset((page - 1) * size).limit(size).all()

            return jsonify({
                "status": "success",
                "total": total,
                "page": page,
                "size": size,
                "posts": [p.to_dict() for p in posts]
            }), 200

        except Exception as e:
            logger.error(f"获取投稿列表失败: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/posts/<int:post_id>", methods=["GET"])
    def get_post(post_id: int):
        """获取单条投稿详情"""
        try:
            session = get_session()
            post = session.query(Post).filter(Post.id == post_id).first()

            if not post:
                return jsonify({"error": "投稿不存在"}), 404

            return jsonify({
                "status": "success",
                "post": post.to_dict()
            }), 200

        except Exception as e:
            logger.error(f"获取投稿详情失败: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/posts/<int:post_id>/reject", methods=["POST"])
    def reject_post(post_id: int):
        """拒绝投稿（标记为 rejected）"""
        try:
            session = get_session()
            post = session.query(Post).filter(Post.id == post_id).first()

            if not post:
                return jsonify({"error": "投稿不存在"}), 404

            post.status = "rejected"
            session.commit()

            logger.info(f"投稿 {post_id} 已标记为拒绝")
            return jsonify({
                "status": "success",
                "message": "投稿已拒绝",
                "post": post.to_dict()
            }), 200

        except Exception as e:
            logger.error(f"拒绝投稿失败: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/posts/sync-to-halo", methods=["POST"])
    def sync_to_halo():
        """
        将待同步的投稿同步到 Halo 博客

        Request Body (可选):
        {
            "post_ids": [1, 2, 3],  // 指定投稿ID，不传则同步所有 pending 状态
            "mode": "append"        // append: 追加到已有文章, new: 创建新文章
        }

        追加模式：将多条投稿合并到一篇 Halo 文章中
        """
        try:
            halo_enabled = config.halo.get("enabled", False)
            if not halo_enabled:
                return jsonify({
                    "status": "skipped",
                    "message": "Halo 同步已禁用（config.json 中 halo.enabled = false）",
                    "hint": "如需启用，请将 config.json 中的 halo.enabled 设为 true"
                }), 200

            body = request.get_json(silent=True) or {}
            post_ids = body.get("post_ids")
            mode = body.get("mode", "new")

            session = get_session()
            query = session.query(Post).filter(Post.status == "pending")

            if post_ids:
                query = query.filter(Post.id.in_(post_ids))

            posts = query.order_by(Post.created_at.asc()).all()

            if not posts:
                return jsonify({
                    "status": "success",
                    "message": "没有待同步的投稿",
                    "synced_count": 0
                }), 200

            if mode == "append":
                result = _sync_posts_append_mode(posts, halo_client, session, logger)
            else:
                result = _sync_posts_new_mode(posts, halo_client, session, logger)

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"同步到 Halo 失败: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    def _sync_posts_new_mode(posts, halo_client, session, logger):
        """每条投稿创建一篇新文章"""
        success_count = 0
        error_count = 0

        for post in posts:
            try:
                halo_result = halo_client.create_post(
                    title=post.title,
                    content=post.to_markdown(),
                    tags=post.tags
                )

                halo_post_name = halo_result.get("metadata", {}).get("name", "")
                post.status = "synced"
                post.halo_post_id = halo_post_name
                post.synced_at = datetime.now()
                session.commit()

                success_count += 1
                logger.info(f"投稿 {post.id} 已同步到 Halo，文章 name: {halo_post_name}")

            except Exception as e:
                error_count += 1
                logger.error(f"同步投稿 {post.id} 失败: {str(e)}", exc_info=True)

        return {
            "status": "completed",
            "mode": "new",
            "total": len(posts),
            "synced_count": success_count,
            "error_count": error_count
        }

    def _sync_posts_append_mode(posts, halo_client, session, logger):
        """将多条投稿追加到一篇已有文章"""
        if not posts:
            return {
                "status": "completed",
                "mode": "append",
                "total": 0,
                "synced_count": 0
            }

        combined_content = "# 校园墙投稿合集\n\n"
        combined_content += f"共 {len(posts)} 条投稿\n\n---\n\n"

        for i, post in enumerate(posts, 1):
            combined_content += f"## 投稿 {i}: {post.title}\n\n"
            combined_content += post.to_markdown()
            combined_content += "\n\n---\n\n"

        title = f"校园墙投稿合集 ({datetime.now().strftime('%Y-%m-%d')})"

        try:
            halo_result = halo_client.create_post(
                title=title,
                content=combined_content,
                tags=["校园墙投稿"]
            )

            halo_post_name = halo_result.get("metadata", {}).get("name", "")

            for post in posts:
                post.status = "synced"
                post.halo_post_id = halo_post_name
                post.synced_at = datetime.now()

            session.commit()

            logger.info(f"{len(posts)} 条投稿已合并同步到 Halo，文章 name: {halo_post_name}")

            return {
                "status": "completed",
                "mode": "append",
                "total": len(posts),
                "synced_count": len(posts),
                "halo_post_id": halo_post_name
            }

        except Exception as e:
            logger.error(f"合并同步失败: {str(e)}", exc_info=True)
            raise

    @app.route("/api/tduck/sync", methods=["POST"])
    def sync_tduck_data():
        """
        手动触发 tduck 数据同步

        从 tduck API 获取所有表单数据并存入数据库。
        用于首次迁移或补同步历史数据。

        Request Body (可选):
        {
            "start_time": "2026-03-01 00:00:00",
            "end_time": "2026-03-14 23:59:59"
        }
        """
        logger.info("收到手动同步请求")

        try:
            body = request.get_json(silent=True) or {}
            start_time = body.get("start_time")
            end_time = body.get("end_time")

            if start_time or end_time:
                data = tduck_client.get_form_data(
                    page=1,
                    size=1000,
                    start_time=start_time,
                    end_time=end_time
                )
                records = data.get("records", [])
            else:
                records = tduck_client.get_all_form_data()

            logger.info(f"获取到 {len(records)} 条记录，开始同步...")

            from src.hooks.questionnaire_parser import parse_questionnaire
            from src.hooks.content_filter import filter_content

            session = get_session()
            success_count = 0
            skip_count = 0
            error_count = 0

            for record in records:
                try:
                    parsed_data = parse_questionnaire(record)

                    filtered_result = filter_content(parsed_data)
                    if not filtered_result["passed"]:
                        logger.warning(f"跳过记录 {record.get('id')}: 未通过敏感词过滤")
                        skip_count += 1
                        continue

                    filtered_data = filtered_result["data"]

                    existing = session.query(Post).filter(
                        Post.tduck_id == filtered_data.get("tduck_id")
                    ).first()

                    if existing:
                        logger.debug(f"记录 {filtered_data.get('tduck_id')} 已存在，跳过")
                        skip_count += 1
                        continue

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
                        tduck_id=filtered_data.get("tduck_id"),
                        tduck_serial=filtered_data.get("tduck_serial"),
                        raw_data=filtered_data.get("raw_data"),
                    )
                    session.add(post)
                    session.commit()

                    success_count += 1
                    logger.info(f"成功同步记录 {filtered_data.get('tduck_id')}: {filtered_data['title']}")

                except ValueError as e:
                    logger.warning(f"跳过无效记录 {record.get('id')}: {e}")
                    skip_count += 1

                except Exception as e:
                    logger.error(f"同步记录 {record.get('id')} 失败: {e}")
                    error_count += 1

            return jsonify({
                "status": "completed",
                "total": len(records),
                "success": success_count,
                "skipped": skip_count,
                "error": error_count
            }), 200

        except Exception as e:
            logger.error(f"同步数据时发生错误: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/tduck/fields", methods=["GET"])
    def get_tduck_fields():
        """
        获取 tduck 表单字段定义

        用于查看表单字段ID，方便配置 questionnaire_parser.py
        """
        try:
            fields = tduck_client.get_form_fields()
            return jsonify({
                "status": "success",
                "fields": [
                    {
                        "value": f.get("value"),
                        "label": f.get("label"),
                        "type": f.get("type")
                    }
                    for f in fields
                ]
            }), 200

        except Exception as e:
            logger.error(f"获取字段定义失败: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/test/halo", methods=["GET"])
    def test_halo_connection():
        """测试 Halo 博客连接"""
        if not halo_client:
            return jsonify({
                "status": "disabled",
                "message": "Halo 同步已禁用",
                "hint": "请将 config.json 中的 halo.enabled 设为 true"
            }), 200
        try:
            result = halo_client.test_connection()
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/test/halo/categories", methods=["GET"])
    def get_halo_categories():
        """
        获取 Halo 分类列表

        返回分类的 metadata.name，配置时需要使用这个 name 而不是显示名称
        """
        if not halo_client:
            return jsonify({
                "status": "disabled",
                "message": "Halo 同步已禁用"
            }), 200
        try:
            categories = halo_client.list_categories()
            return jsonify({
                "status": "success",
                "categories": categories,
                "hint": "配置 config.json 中的 default_category 时，请使用 name 字段的值"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/test/halo/tags", methods=["GET"])
    def get_halo_tags():
        """
        获取 Halo 标签列表

        返回标签的 metadata.name，配置时需要使用这个 name 而不是显示名称
        """
        if not halo_client:
            return jsonify({
                "status": "disabled",
                "message": "Halo 同步已禁用"
            }), 200
        try:
            tags = halo_client.list_tags()
            return jsonify({
                "status": "success",
                "tags": tags,
                "hint": "配置 config.json 中的 default_tags 时，请使用 name 字段的值"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/test/tduck", methods=["GET"])
    def test_tduck_connection():
        """测试 tduck API 连接"""
        try:
            fields = tduck_client.get_form_fields()
            return jsonify({
                "status": "ok",
                "message": f"成功连接到 tduck API，表单包含 {len(fields)} 个字段"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/scheduler/status", methods=["GET"])
    def get_scheduler_status():
        """
        获取定时任务状态

        返回定时任务是否运行、下次执行时间等信息
        """
        try:
            from src.scheduler import get_scheduler_status
            status = get_scheduler_status()
            return jsonify({
                "status": "success",
                "scheduler": status
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/scheduler/run", methods=["POST"])
    def run_sync_manually():
        """
        手动触发一次同步

        立即从 tduck API 获取数据并同步到数据库
        """
        try:
            from src.scheduler import sync_tduck_data
            sync_tduck_data()
            return jsonify({
                "status": "success",
                "message": "同步任务已执行"
            })
        except Exception as e:
            logger.error(f"手动同步失败: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/posts/create", methods=["POST"])
    def create_post_manually():
        """
        手动创建投稿（用于测试）

        Request Body:
        {
            "title": "投稿标题",
            "content": "投稿内容",
            "class_name": "班级（可选）",
            "user_name": "姓名（可选）",
            "wx_nickname": "微信昵称（可选）"
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求体为空"}), 400

            title = data.get("title")
            content = data.get("content")

            if not title or not content:
                return jsonify({"error": "标题和内容不能为空"}), 400

            from src.hooks.content_filter import filter_content

            post_data = {
                "title": title,
                "content": content,
                "class_name": data.get("class_name"),
                "user_name": data.get("user_name"),
                "wx_nickname": data.get("wx_nickname"),
                "wx_openid": data.get("wx_openid"),
                "tags": data.get("tags", []),
            }

            filtered_result = filter_content(post_data)
            if not filtered_result["passed"]:
                return jsonify({
                    "status": "filtered",
                    "reason": filtered_result["reason"]
                }), 200

            filtered_data = filtered_result["data"]

            session = get_session()
            post = Post(
                title=filtered_data["title"],
                content=filtered_data["content"],
                class_name=filtered_data.get("class_name"),
                user_name=filtered_data.get("user_name"),
                wx_nickname=filtered_data.get("wx_nickname"),
                wx_openid=filtered_data.get("wx_openid"),
                tags=filtered_data.get("tags", []),
                status="pending",
            )
            session.add(post)
            session.commit()

            logger.info(f"手动创建投稿成功，ID: {post.id}")
            return jsonify({
                "status": "success",
                "message": "投稿创建成功",
                "post": post.to_dict()
            }), 200

        except Exception as e:
            logger.error(f"创建投稿失败: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/webhook/questionnaire", methods=["POST"])
    def handle_questionnaire_webhook_legacy():
        """兼容旧版问卷星 Webhook 接口（已弃用）"""
        logger.warning("收到旧版问卷星 Webhook 请求，请迁移到 /webhook/tduck")
        return jsonify({
            "error": "已弃用",
            "message": "请使用新的 Webhook 端点: /webhook/tduck"
        }), 410

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """请求结束后自动关闭数据库会话"""
        from src.database import _session_factory
        if _session_factory is not None:
            _session_factory.remove()

    return app


def main():
    """主函数，启动 Flask 应用"""
    app = create_app()
    app_config = config.app

    host = app_config.get("host", "0.0.0.0")
    port = app_config.get("port", 5000)
    debug = app_config.get("debug", False)

    from src.scheduler import start_scheduler
    start_scheduler()

    print(f"[启动] 校园墙同步服务正在启动...")
    print(f"[启动] 监听地址: http://{host}:{port}")
    print(f"[启动] tduck Webhook: http://{host}:{port}/webhook/tduck")
    print(f"[启动] 健康检查: http://{host}:{port}/health")
    print(f"[启动] 投稿列表: http://{host}:{port}/api/posts")

    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        from src.scheduler import stop_scheduler
        stop_scheduler()


if __name__ == "__main__":
    main()
