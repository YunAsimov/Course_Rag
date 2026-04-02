# COMP5575 Course RAG

一个面向课程讲义、笔记和参考资料的轻量 RAG MVP。项目内置本地检索和前端问答界面，不配置远程 API 也可以直接运行。

## 功能

- 当前默认只索引 `data/course` 下的 `md` 课程资料
- 使用本地 BM25 风格检索构建可运行的 RAG 基线
- 可选接入 OpenAI 兼容接口进行远程生成
- 提供一个简单的 Flask Web 问答界面，展示答案和来源片段
- 默认索引 `data/course` 目录下的 Markdown 课程资料
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

## 目录说明

- `app.py`: Flask 入口
- `utils/rag_service.py`: 按用户管理资料目录、索引和问答主流程
- `utils/local_store.py`: MySQL 用户、历史和资料元数据存储
- `dashboard.html`、`auth.html`、`styles.css`、`app.js`、`auth.js`: Web 前端页面资源
- `config/`: RAG、检索、提示词和模型配置
- `data/course/`: 当前默认课程资料目录
- `storage/materials/<username>/`: 每个用户自己的资料文件目录

## 当前实现说明

- 检索阶段使用轻量本地 BM25 检索器，适合课程项目和快速原型
- 若未开启远程大模型，答案由本地摘要器根据检索片段生成
- PDF 解析依赖 `pypdf`，复杂排版文件的抽取质量取决于原始 PDF 文本层
