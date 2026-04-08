# Course RAG

一个面向课程讲义、笔记和参考资料的课程问答 Web 系统。当前版本已经实现多用户资料隔离、MySQL 持久化、Hybrid Retrieval（BM25 + Embedding）、可选远程大模型生成，以及适配 1Panel 的部署方案。

## 项目概述

系统围绕课程资料构建问答能力，核心目标是让用户围绕讲义、课堂笔记和补充资料进行基于证据的提问，而不是依赖通用模型进行无依据生成。

当前运行链路分为三部分：

1. 文档处理：扫描课程资料文件，完成格式解析、清洗、分段和切块。
2. 混合检索：同时执行 BM25 检索和 embedding 语义检索，再进行融合排序。
3. 回答生成：优先调用 OpenAI 兼容接口生成答案；若远程模型不可用，则回退到本地摘要模式。

## 当前实现状态

### 已完成

- 基于 Flask 的课程问答 Web 应用
- 登录、退出、历史记录查看与删除
- 用户级资料目录隔离：`storage/materials/<username>/`
- 文件上传、查看、删除与索引刷新
- MySQL 持久化：用户、历史记录、资料元数据
- Hybrid Retrieval：BM25 + Embedding
- Embedding 检索失败时自动回退到 BM25
- 远程大模型生成与本地摘要回退
- 启动阶段“知识库索引构建中”前端提示
- Docker / Gunicorn / 1Panel 部署支持

### 当前技术边界

- 已实现的是 Hybrid Retrieval，不再是纯 BM25 基线
- 已接入本地持久化向量库 Chroma，用于保存 embedding 向量和集合索引
- embedding 向量在首次构建或资料变更时通过远程接口计算，并落盘到 `storage/vector_store/chroma/`
- 因此当前方案属于“BM25 + 持久化 Chroma 向量库”的混合检索实现，而不是仅内存 embedding 的临时方案

## 检索架构

### 1. 文档加载与切块

资料目录分为两类：

- `data/course/`：公共课程资料，仅用于未登录状态下的启动页统计与默认公共索引
- `storage/materials/<username>/`：当前用户私有资料，用户登录后的问答、文件管理和索引都基于这里

默认允许的文件类型目前为：

- `.md` / `.markdown`
- `.txt`
- `.pdf`
- `.docx`
- `.csv` / `.tsv`
- `.json`
- `.html` / `.htm`
- `.pptx`

切块相关参数位于 `config/chroma.yml`：

- `chunk_size: 420`
- `chunk_overlap: 80`
- `top_k: 4`
- `candidate_top_k: 12`

### 2. BM25 检索

本地 BM25 检索负责：

- 中英文轻量分词
- 词频与逆文档频率统计
- 标题与章节标题加权
- 返回关键词匹配较强的候选 chunk

### 3. Embedding 检索与持久化向量库

系统通过 OpenAI 兼容接口调用 embedding 模型：

- 默认模型：`text-embedding-v4`
- 默认接口：`https://dashscope.aliyuncs.com/compatible-mode/v1`

embedding 检索流程如下：

1. 将每个 chunk 序列化为检索文本
2. 调用远程 embedding 接口生成向量
3. 对向量做归一化
4. 将向量写入本地持久化 Chroma 集合
5. 查询时将 query 向量提交给 Chroma 进行相似度召回
6. 返回语义相关候选

当前为了兼容 DashScope 接口，embedding 批量大小已限制为 `10`。

### 4. 融合策略

Hybrid Retrieval 使用 BM25 与 Embedding 并行召回，再通过融合排序合并结果。当前实现采用基于排名的融合方法，主要参数包括：

- `bm25_weight`
- `embedding_weight`
- `rrf_k`
- `candidate_top_k`

最终检索后端在健康检查接口中可见：

- `local_bm25`
- `hybrid_bm25_embedding`

其中：

- `hybrid_bm25_embedding` 表示 BM25 与 embedding 都已可用
- `local_bm25` 表示当前配置虽然允许混合检索，但 embedding 配置缺失或远程请求失败，系统已自动回退到 BM25

## 启动与索引机制

当前版本已经把索引构建改为异步后台执行：

- 服务会先启动并监听 `127.0.0.1:7860`
- 前端在登录页和主页面显示“知识库索引构建中”提示
- 后端 `/api/health` 会返回：
  - `status`
  - `ready`
  - `indexing`
  - `message`
- 索引完成后，前端自动恢复登录与提问能力

对于默认公共课程资料，当前本地环境下大约会构建：

- `10` 份文档
- `215` 个检索切片

在启用 Hybrid Retrieval 时，首次启动或资料变更后通常需要额外时间来完成 embedding 向量构建；后续重启会优先复用已落盘的 Chroma 向量集合，只同步新增、变更或删除的 chunk。

## 生成模式

回答生成支持三种运行结果：

- `remote_llm`：远程大模型成功生成
- `local_summary`：远程模型不可用时由本地摘要器组织答案
- `no_context`：当前知识库中没有足够相关资料
- `indexing`：索引尚未构建完成，系统提示稍后再问

## 多用户与数据隔离

系统按用户隔离以下内容：

- 资料目录
- 历史记录
- 资料元数据
- 用户视角下的知识库索引

这意味着不同用户即使提问同样的问题，只要资料目录不同，结果就可能不同。

当前登录页已经关闭自助注册。新增用户需要由管理员通过数据库或管理脚本创建账号。

## MySQL 持久化

系统使用 MySQL `course_rag` 数据库保存：

- `users`
- `history`
- `user_materials`

数据库连接参数从 `.env.local` 读取，例如：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`

其中用户密码以哈希形式存储，运行时不会以明文保存在数据库中。

## 本地运行

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2. 配置 `.env.local`

示例：

```env
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_API_KEY=your_api_key
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=course_rag
```

### 3. 启动应用

```bash
python app.py
```

### 4. 打开页面

```text
http://127.0.0.1:7860
```

## 健康检查

访问：

```text
GET /api/health
```

索引构建中时会返回类似：

```json
{
  "backend": "initializing",
  "chunks": 0,
  "documents": 0,
  "indexing": true,
  "message": "知识库索引构建中，请稍候。",
  "ready": false,
  "status": "indexing"
}
```

索引完成后会返回类似：

```json
{
  "backend": "hybrid_bm25_embedding",
  "chunks": 215,
  "documents": 10,
  "indexing": false,
  "message": "知识库已准备就绪。",
  "ready": true,
  "status": "ok"
}
```

说明：

- 未登录访问 `/api/health` 时，返回的是公共资料目录 `data/course/` 的状态
- 登录后访问 `/api/health` 时，返回的是当前用户私有资料目录的状态
- 因此不同用户看到的 `documents`、`chunks` 和 `backend` 可能不同

## 项目结构

```text
RAG/
├─ app.py
├─ run_app_latest.py
├─ requirements.txt
├─ Dockerfile
├─ gunicorn.conf.py
├─ README.md
├─ report.md
├─ config/
├─ data/course/
├─ storage/materials/<username>/
├─ deploy/1panel/
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

- `course_rag/web.py`
  Flask 路由、登录态、文件管理和健康检查接口

- `course_rag/core/config_handler.py`
  YAML 配置、默认配置、本地环境变量读取

- `course_rag/services/rag_service.py`
  用户级 RAG 服务管理、异步索引构建、问答主流程

- `course_rag/services/rag_retriever.py`
  BM25、EmbeddingRetriever、HybridRetriever

- `course_rag/services/rag_generator.py`
  远程生成与本地摘要回退

- `course_rag/persistence/store.py`
  MySQL 用户、历史记录和资料元数据读写


## 检索评测集

项目现在包含一套基础检索评测集，用于评估当前检索后端对课程问题的 Top-k 召回能力。

评测数据文件：

- `eval/retrieval_eval_public.json`

运行方式：

```bash
python run_retrieval_eval.py
```

若未激活虚拟环境，建议直接使用项目虚拟环境解释器：

```powershell
.\.venv\Scripts\python.exe run_retrieval_eval.py
```

可选参数：

- `--dataset`：指定评测集文件
- `--data-dir`：指定评测使用的数据目录
- `--top-k`：指定评测时使用的 top-k
- `--output`：指定结果 JSON 输出路径
- `--show-passed`：打印所有样例结果

默认会输出：

- `Hit@1`
- `Hit@3`
- `Hit@k`
- `MRR`

并将完整评测结果写入：

- `eval/results/retrieval_eval_latest.json`

## 1Panel 部署

项目已经包含部署文件：

- `Dockerfile`
- `gunicorn.conf.py`
- `deploy/1panel/docker-compose.yml`
- `deploy/1panel/.env.example`
- `deploy/1panel/README.md`

推荐部署方式：

1. 用 1Panel 编排导入 `deploy/1panel/docker-compose.yml`
2. 启动 `app + mysql` 容器
3. 用 1Panel 网站模块创建反向代理
4. 将外部请求代理到 `127.0.0.1:17860`

## 当前局限

- 当前采用的是本地单机 Chroma 持久化向量库，还不是独立服务化的向量数据库集群
- 首次建库或大规模资料变更时，启动时间仍会随资料数量和 embedding 网络延迟增长
- 目前仍缺少更细粒度的增量索引策略
- 自动化测试覆盖仍然不足

## 后续改进方向

- 将当前本地 Chroma 演进为更强的向量存储方案（如 pgvector 或服务化向量数据库）
- 进一步细化增量索引，仅为新增或变更资料重算 embedding
- 增加 rerank 层提升最终召回质量
- 完善管理员侧用户与资料管理功能
- 增加单元测试、接口测试和部署检查
