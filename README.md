# COMP5575 Course RAG

一个面向课程讲义、笔记和参考资料的轻量 RAG Web 项目。项目支持本地 BM25 检索、可选远程大模型生成、按用户隔离的资料目录，以及 MySQL 持久化用户与历史记录。

## 功能

- 默认索引 `data/course` 下的 Markdown 课程资料
- 使用本地 BM25 风格检索构建可运行的 RAG 基线
- 可选接入 OpenAI 兼容接口进行远程生成
- 提供 Flask Web 问答界面，展示答案和来源片段
- 不同用户拥有各自独立的资料目录，互不共享上传文件
- 账号、历史记录和资料元数据持久化到 MySQL `course_rag`

## 快速启动

1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

2. 启动应用

```bash
python app.py
```

3. 打开浏览器

访问 `http://127.0.0.1:7860`

## 可选启用远程大模型

默认配置下，项目使用本地摘要模式回答问题。若要启用远程模型：

1. 在 `config/agent.yml` 中把 `enabled` 改为 `true`
2. 在项目根目录创建 `.env.local`，至少包含 `OPENAI_API_KEY`
3. 如需覆盖默认地址，可在 `.env.local` 中配置 `OPENAI_BASE_URL`
4. 如有需要，修改 `model_name`

## MySQL 存储

项目默认从根目录 `.env.local` 读取数据库配置：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`

当前实现会在启动时自动创建 `course_rag` 数据库和所需表结构。

## 目录结构

```text
RAG/
├─ app.py
├─ run_app_latest.py
├─ requirements.txt
├─ config/
├─ data/course/
├─ storage/materials/<username>/
└─ course_rag/
   ├─ __init__.py
   ├─ web.py
   ├─ core/
   ├─ persistence/
   ├─ services/
   ├─ templates/
   └─ static/
```

## 关键模块

- `course_rag/web.py`: Flask 路由、登录态和上传/问答接口
- `course_rag/core/`: 配置、路径、日志和文件加载
- `course_rag/services/`: 检索、切块、生成和用户索引管理
- `course_rag/persistence/store.py`: MySQL 用户、历史和资料元数据存储
- `course_rag/templates/`: 页面模板
- `course_rag/static/`: 前端 CSS/JS 资源

## 当前实现说明

- 检索阶段使用轻量本地 BM25 检索器，适合课程项目和快速原型
- 若未开启远程大模型，答案由本地摘要器根据检索片段生成
- 资料文件按用户隔离在 `storage/materials/<username>/`

## 1Panel 部署

项目已经补好了容器化部署文件，适合直接放到 1Panel。

- `Dockerfile`
- `gunicorn.conf.py`
- `deploy/1panel/docker-compose.yml`
- `deploy/1panel/.env.example`
- `deploy/1panel/README.md`

推荐使用 1Panel 的 `容器 -> 编排` 导入 `deploy/1panel/docker-compose.yml`，然后再用 `网站 -> 创建网站 -> 反向代理` 把域名代理到 `127.0.0.1:17860`。
