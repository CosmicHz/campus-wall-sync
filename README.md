# campus-wall-sync 校园墙同步服务

将 tduck 表单收到的投稿自动存入数据库，支持人工/AI 审核，后续可同步到 Halo 博客。

## 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        投稿处理流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  tduck 表单提交                                                  │
│      ↓                                                          │
│  Webhook 触发 / 定时同步                                         │
│      ↓                                                          │
│  解析表单数据 (questionnaire_parser.py)                          │
│      ↓                                                          │
│  敏感词过滤 (content_filter.py)                                  │
│      ↓                                                          │
│  存入数据库 (状态: pending)                                      │
│      ↓                                                          │
│  [可选] 同步到 Halo 博客 (需启用 halo.enabled)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```


## 协作分工

```
┌─────────────────────────────────────────────────────────────┐
│                        项目成员                              │
├─────────────────────────┬───────────────────────────────────┤
│      开发组（学生）       │            运维组                 │
│  只改 src/hooks/ 目录    │     只管部署和基础设施              │
│  • 表单解析逻辑           │     • Docker/1Panel               │
│  • 敏感词过滤            │     • 服务器维护                    │
│  • AI审核配置           │     • CI/CD 流水线                  │
│  • 业务流程调整          │     • 监控告警                     │
└─────────────────────────┴───────────────────────────────────┘
```


## 快速开始

### 1. 本地开发（Windows/Mac/Linux）

```bash
# 方式一：Windows 双击运行
run_local.bat

# 方式二：命令行
pip install -r requirements.txt
python -m src.app
```
启动服务后，打开浏览器访问 `http://localhost:5000/admin` 开发后台管理界面。

### 2. 配置服务

复制配置文件并填写配置：

```bash
cp config.json.example config.json
```

编辑 `config.json`：

```json
{
    "app": {
        "debug": false,
        "host": "0.0.0.0",
        "port": 5000
    },
    "database": {
        "path": "data/campus_wall.db"
    },
    "halo": {
        "enabled": false,
        "api_url": "https://你的Halo博客地址",
        "api_token": "你的API Token"
    },
    "tduck": {
        "enabled": true,
        "api_key": "你的tduck API Key",
        "base_url": "https://x.tduckcloud.com",
        "field_ids": {
            "class": "inputxxx",
            "name": "inputyyy",
            "content": "textareazzz"
        },
        "sync": {
            "enabled": true,
            "interval_minutes": 5
        }
    },
    "content_filter": {
        "replace_mode": true
    }
}
```

### 3. 启动服务

```bash
python -m src.app
```

服务启动后访问：
- 健康检查: http://localhost:5000/health
- 投稿列表: http://localhost:5000/api/posts
- 查看字段定义: http://localhost:5000/api/tduck/fields


## 配置说明

### Halo 同步开关

```json
{
    "halo": {
        "enabled": false,    // 设为 true 启用同步到 Halo
        "api_url": "...",
        "api_token": "..."
    }
}
```

| 值 | 行为 |
|----|------|
| `false` | 只存数据库，不同步到 Halo |
| `true` | 存数据库 + 同步到 Halo |

### tduck 定时同步

```json
{
    "tduck": {
        "sync": {
            "enabled": true,           // 启用定时同步
            "interval_minutes": 5      // 每 5 分钟同步一次
        }
    }
}
```

### 敏感词过滤模式

```json
{
    "content_filter": {
        "replace_mode": true    // true: 替换为***后通过, false: 直接拒绝
    }
}
```

### 配置热更新

修改配置后无需重启服务，调用 API 即可生效：

```bash
# 1. 修改 config.json
vim config.json

# 2. 热更新配置
curl -X POST http://localhost:5000/api/config/reload
```

**支持热更新的配置：**
- `tduck.api_key` - tduck API 密钥
- `halo.api_token` - Halo API Token
- `tduck.field_ids.*` - 表单字段映射
- `review.*` - 审核配置
- `content_filter.*` - 内容过滤配置

**不支持热更新（需重启）：**
- `database.path` - 数据库路径
- `app.host` / `app.port` - 服务地址和端口


## API 接口

### 投稿管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/posts` | GET | 获取投稿列表（支持分页、状态筛选） |
| `/api/posts/<id>` | GET | 获取单条投稿详情 |
| `/api/posts/<id>/reject` | POST | 拒绝投稿 |
| `/api/posts/sync-to-halo` | POST | 同步到 Halo（需启用 halo.enabled） |

### tduck 相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/webhook/tduck` | POST | 接收 tduck Webhook |
| `/api/tduck/sync` | POST | 手动同步 tduck 历史数据 |
| `/api/tduck/fields` | GET | 获取表单字段定义 |

### 定时任务

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/scheduler/status` | GET | 查看定时任务状态 |
| `/api/scheduler/run` | POST | 手动触发一次同步 |

### 配置管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/config/reload` | POST | 热更新配置（无需重启） |
| `/api/config/info` | GET | 查看当前配置 |

### 测试接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/test/halo` | GET | 测试 Halo 连接 |
| `/test/halo/categories` | GET | 获取 Halo 分类列表 |
| `/test/halo/tags` | GET | 获取 Halo 标签列表 |
| `/test/tduck` | GET | 测试 tduck API 连接 |


## 投稿状态

| 状态 | 说明 |
|------|------|
| `pending` | 待同步 |
| `synced` | 已同步到 Halo |
| `rejected` | 已拒绝 |


## 同步到 Halo

> **注意**：需先在 `config.json` 中设置 `halo.enabled = true`

### 方式一：每条投稿创建一篇新文章

```bash
POST /api/posts/sync-to-halo
Content-Type: application/json

{
    "mode": "new"
}
```

### 方式二：合并多条投稿到一篇文章

```bash
POST /api/posts/sync-to-halo
Content-Type: application/json

{
    "mode": "append"
}
```

### 指定投稿 ID 同步

```bash
POST /api/posts/sync-to-halo
Content-Type: application/json

{
    "post_ids": [1, 2, 3],
    "mode": "new"
}
```


## tduck 表单配置

### 1. 获取 API Key

在 tduck 后台 → 对应表单 → 发布 → 数据推送 中获取 API Key。

### 2. 获取字段 ID

启动服务后访问：
```
GET http://localhost:5000/api/tduck/fields
```

返回示例：
```json
{
    "status": "success",
    "fields": [
        {"value": "input1779702655117", "label": "班级", "type": "INPUT"},
        {"value": "input1779702656732", "label": "姓名", "type": "INPUT"},
        {"value": "textarea1779702658038", "label": "投稿内容", "type": "TEXTAREA"}
    ]
}
```

将字段 ID 填入 `config.json`：
```json
{
    "tduck": {
        "field_ids": {
            "class": "input1779702655117",
            "name": "input1779702656732",
            "content": "textarea1779702658038"
        }
    }
}
```


## 开发指南

### 修改业务逻辑

所有业务代码都在 `src/hooks/` 目录下：

| 文件 | 功能 | 修改时机 |
|------|------|----------|
| `questionnaire_parser.py` | 解析 tduck 表单数据 | 表单字段有变化时 |
| `content_filter.py` | 敏感词过滤 | 需要调整审核规则时 |

### 添加敏感词

修改 `src/hooks/content_filter.py`：

```python
SENSITIVE_WORDS = [
    "敏感词1",
    "敏感词2",
]
```


## 部署指南（运维组）

### 使用 Docker Compose

```bash
# 1. 克隆项目
git clone <仓库地址>
cd campus-wall-sync

# 2. 配置生产环境
cp config.json.example config.json
# 编辑 config.json 填写生产配置

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

### 数据持久化

数据库文件存储在 `data/campus_wall.db`，已通过 Docker Volume 持久化。


## 数据库结构

### posts 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| title | VARCHAR(255) | 投稿标题 |
| content | TEXT | 投稿内容 |
| class_name | VARCHAR(50) | 班级 |
| user_name | VARCHAR(50) | 姓名 |
| wx_nickname | VARCHAR(100) | 微信昵称 |
| status | VARCHAR(20) | 状态 |
| tduck_id | INTEGER | tduck 记录 ID |
| halo_post_id | VARCHAR(50) | Halo 文章 ID |
| raw_data | JSON | 原始数据 |
| created_at | DATETIME | 创建时间 |


## License

MIT License
