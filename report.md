# Course RAG

## 课程项目报告

**课程名称：** COMP5575 High-Dimensional Data Management and Analytics  
**项目名称：** Course RAG：基于课程资料的混合检索增强问答系统  
**项目类型：** 课程项目 / 系统实现报告  
**提交形式：** Markdown 项目报告

---

## 摘要

本项目实现了一个面向课程讲义、课堂笔记和补充资料的课程问答系统。系统采用检索增强生成思路，将课程资料切分为多个文本片段，在回答问题前先从知识库中检索相关内容，再结合远程大模型或本地摘要模块生成回答。与早期仅使用 BM25 的检索基线不同，当前版本已经升级为 Hybrid Retrieval，即同时使用 BM25 词项检索和 embedding 语义检索，再通过融合排序得到最终候选结果。这样既能保留关键词匹配的稳定性，也能增强对语义相近但词面不同问法的适应能力。

系统当前支持多用户登录、用户级资料目录隔离、历史记录管理、文件上传与删除、MySQL 持久化，以及 1Panel 容器化部署。针对混合检索带来的启动耗时问题，项目进一步将索引构建改为异步后台执行，并在前端加入“知识库索引构建中”的状态提示，使页面能够先于完整索引构建过程启动。当前实现已经形成从数据组织、检索、生成、前后端交互、数据库持久化到部署上线的完整工程闭环。

需要明确的是，本项目当前虽然已经实现 embedding 检索并与 BM25 融合，但尚未接入独立的向量数据库。embedding 向量由远程接口在服务启动阶段生成，并保存在内存中参与召回。因此，系统属于“BM25 + in-memory embedding index”的混合检索实现，而不是“embedding + persistent vector DB”的最终生产形态。这也是项目现阶段的主要工程边界和后续优化重点。

## 关键词

RAG；课程资料问答；Hybrid Retrieval；BM25；Embedding；向量化；多用户隔离；MySQL 持久化

---

## 1. 引言

### 1.1 研究背景

在课程问答场景中，用户的问题通常具有明确资料边界。例如，学生会围绕课程时间安排、考试范围、概念定义、算法推导和章节总结进行提问。这类问题与开放域闲聊不同，更强调答案必须来源于课程资料本身，而不是依赖模型记忆进行自由生成。若缺乏检索环节，大模型虽然可以生成流畅文本，但容易出现事实偏差、课程信息过期或回答无依据的问题。

检索增强生成（Retrieval-Augmented Generation, RAG）正适合这类场景。其基本思想是先从外部知识库中召回与问题相关的文本片段，再将这些片段作为上下文交给生成模块，以提升回答的可追溯性和可靠性。对于课程资料系统而言，这意味着系统不仅要“会回答”，更要“依据资料回答”。

### 1.2 项目目标

本项目的核心目标如下：

- 构建一个面向课程讲义、课堂笔记和参考资料的课程问答系统。
- 让回答尽量基于当前知识库中的课程资料，而非无依据生成。
- 实现多用户系统，使不同用户拥有各自独立的资料目录与历史记录。
- 将系统从单一 BM25 检索升级为 Hybrid Retrieval。
- 支持远程大模型生成，并保留远程不可用时的本地回退能力。
- 支持 MySQL 持久化和 1Panel 部署。
- 保持系统具有较清晰的工程结构和后续可扩展性。

### 1.3 报告结构

本报告依次介绍项目需求、总体设计、检索与向量化实现、系统功能、部署与运行效果、当前局限及改进方向，以完整概括项目的实现过程与现状。

---

## 2. 需求分析

### 2.1 功能需求

本项目围绕课程资料问答，提出以下核心功能需求：

1. 支持用户登录与退出。
2. 支持围绕课程资料进行自然语言提问。
3. 回答应附带可追溯的来源片段。
4. 支持用户历史记录保存、查看与删除。
5. 支持上传、查看、打开和删除课程资料文件。
6. 不同用户的资料目录和历史记录彼此隔离。
7. 用户、历史记录和资料元数据能够持久化保存。
8. 系统应具备本地运行与服务器部署能力。
9. 登录功能对最终用户开放，但自助注册默认关闭，由管理员创建账号。

### 2.2 非功能需求

除功能需求外，系统还要求具备：

- 可维护性：模块化组织，配置、业务逻辑和持久化层清晰分离。
- 可扩展性：后续可以替换更强检索器或引入向量数据库。
- 可用性：前端界面直观，适合课程资料问答场景。
- 稳定性：远程模型不可用时系统不应完全失效。
- 部署友好性：适配 Docker、Gunicorn 和 1Panel。

---

## 3. 总体设计

### 3.1 系统总体架构

系统整体可分为四层：

1. 表现层  
   基于 Flask 模板和静态前端资源实现登录页、问答页、历史区和文件面板。

2. 业务层  
   负责文档读取、切块、Hybrid Retrieval、回答生成以及用户级知识库管理。

3. 持久化层  
   由 MySQL 存储模块实现用户、历史记录和资料元数据的持久化。

4. 基础设施层  
   负责配置加载、日志、路径与文件处理。

从数据流角度，系统主要流程为：

1. 未登录时，系统基于公共目录 `data/course/` 提供启动页统计与默认健康状态。
2. 用户登录系统后，系统定位当前用户的私有资料目录 `storage/materials/<username>/`。
3. 若当前用户索引尚未完成，则后台构建索引并在前端显示提示。
4. 用户提问后，系统执行混合检索，得到候选资料片段。
5. 生成模块基于检索结果输出回答。
6. 回答与来源保存到历史记录。

### 3.2 项目结构

当前项目结构如下：

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
│  ├─ rag.yml
│  ├─ agent.yml
│  ├─ chroma.yml
│  └─ prompts.yml
├─ data/
│  └─ course/
├─ storage/
│  └─ materials/<username>/
├─ deploy/
│  └─ 1panel/
└─ course_rag/
   ├─ web.py
   ├─ core/
   ├─ persistence/
   ├─ services/
   ├─ templates/
   └─ static/
```

### 3.3 设计原则

本项目遵循以下设计原则：

- 资料优先：回答必须尽量依据课程资料。
- 用户隔离：用户知识库互相独立。
- 可运行优先：在保证系统完整可用的前提下逐步增强检索能力。
- 工程闭环：实现从问答到持久化再到部署的完整链路。

---

## 4. 检索与向量化实现

### 4.1 文档加载与切块

资料加载位于 `course_rag/core/file_handler.py`，切块逻辑位于 `course_rag/services/rag_chunking.py`。

当前系统默认使用 Markdown 资料，其优点包括：

- 结构清晰，标题和段落层级较稳定。
- 噪声少于 PDF 抽取文本。
- 更适合作为课程问答的受控语料。

系统在建立索引时会：

1. 扫描符合扩展名要求的文件。
2. 读取文件内容并构建文档对象。
3. 按 `chunk_size = 420`、`chunk_overlap = 80` 进行切块。
4. 交给检索器建立索引。

### 4.2 BM25 检索

BM25 检索器的实现位于 `course_rag/services/rag_retriever.py`。其主要职责包括：

- 中英文轻量分词。
- 统计词频和逆文档频率。
- 对标题命中与章节标题命中进行加权。
- 返回关键词相关性较高的候选 chunk。

BM25 的优势在于：

- 本地运行，不依赖额外外部服务。
- 对课程资料中关键词明确的问题表现稳定。
- 实现成本较低，便于形成可运行基线。

### 4.3 Embedding 向量化实现

与早期仅预留 embedding 配置不同，当前版本已经真正实现 embedding 检索。其实现路径如下：

1. 将每个 chunk 序列化为检索文本。
2. 使用 OpenAI 兼容接口调用 embedding 模型 `text-embedding-v4`。
3. 对得到的向量进行归一化处理。
4. 将用户问题编码为 query embedding。
5. 通过余弦相似度计算 query 与 chunk 向量之间的语义相似度。

余弦相似度公式如下：

\[
\text{cos}(\theta) = \frac{\mathbf{q} \cdot \mathbf{v}_i}{\|\mathbf{q}\|\|\mathbf{v}_i\|}
\]

其中：

- \(\mathbf{q}\) 表示问题向量
- \(\mathbf{v}_i\) 表示第 \(i\) 个 chunk 向量

当前 embedding 检索的实现特点是：

- 向量由远程接口在索引构建阶段生成。
- 生成后的向量保存在内存中。
- 当前尚未写入独立向量数据库。
- 单次 batch 大小被限制为 `10`，以兼容 DashScope embedding 接口。

### 4.4 Hybrid Retrieval 融合策略

当前系统的检索后端已经从纯 BM25 升级为 `hybrid_bm25_embedding`。实现上，系统会同时执行：

- BM25 关键词检索
- embedding 语义检索

然后利用融合排序合并结果。当前核心参数包括：

- `bm25_weight`
- `embedding_weight`
- `rrf_k`
- `candidate_top_k`

这种设计兼顾了两种检索方式的优势：

- BM25 更擅长精确关键词匹配
- embedding 更擅长处理语义相近但表述不同的问题

需要注意的是，系统虽然默认目标后端是 Hybrid Retrieval，但运行时仍保留回退逻辑。若 embedding 所需配置缺失，或者远程 embedding 请求失败，实际运行后端会自动退回 `local_bm25`，从而保证系统继续可用。

### 4.5 当前技术边界

需要明确指出，当前系统虽然已经实现 Hybrid Retrieval，但仍然不是“embedding + vector DB”的完整落地方案。现阶段的真实状态是：

- 已实现：BM25 + in-memory embedding index
- 未实现：embedding 向量持久化到独立向量数据库

这意味着系统每次重启时，如果索引不存在，就需要重新向量化全部 chunk。因此，Hybrid Retrieval 会显著增加服务启动阶段的索引构建时间。

---

## 5. 生成模块实现

生成逻辑位于 `course_rag/services/rag_generator.py`。

系统当前支持以下回答模式：

- `remote_llm`：远程大模型生成成功。
- `local_summary`：远程模型不可用时由本地摘要器生成。
- `no_context`：当前知识库中没有足够相关内容。
- `indexing`：索引尚在构建中，提示稍候再问。

这种模式设计保证了系统的鲁棒性。即使远程模型、embedding 或索引构建出现问题，系统仍然可以通过回退机制维持基本可用性。

---

## 6. 异步索引构建与启动阶段优化

### 6.1 问题背景

在启用 Hybrid Retrieval 之后，系统启动时不仅要做文档切块，还要对全部 chunk 调用远程 embedding 接口完成向量化。对于当前默认公共资料库，大约需要处理：

- `10` 份文档
- `215` 个 chunk

实际测试表明，这一步通常需要约 `75-80` 秒。如果继续使用同步构建模式，服务在索引完成前不会开始监听端口，用户会直接看到浏览器连接失败。

### 6.2 当前解决方案

当前版本已经将索引改为后台异步构建：

- Flask 服务会先启动并监听 `127.0.0.1:7860`
- 后台线程执行知识库索引构建
- `/api/health` 会返回当前索引状态
- 登录页和主页面前端轮询健康状态，并显示“知识库索引构建中”提示
- 构建完成后自动恢复登录和提问功能

当前健康检查在启动初期会返回类似：

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

索引完成后则变为：

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

### 6.3 工程意义

这一调整的重要意义在于：

- 用户不再把“索引尚未完成”误判为“服务挂掉”。
- 前端启动体验更稳定。
- 启动耗时问题被显式暴露为状态，而不是隐藏为连接错误。

---

## 7. Web 与前端实现

### 7.1 Web 后端

Flask 路由位于 `course_rag/web.py`。主要接口包括：

- `GET /`：问答主页
- `GET /login`：登录页
- `POST /api/auth/login`：登录接口
- `POST /api/auth/register`：接口保留，但当前固定返回 403，表示自助注册已关闭
- `POST /api/auth/logout`：退出接口
- `GET /api/auth/me`：读取登录态
- `POST /api/ask`：提问接口
- `GET /api/history`：读取历史记录
- `DELETE /api/history/<record_id>`：删除历史记录
- `POST /api/upload`：上传资料
- `GET /api/files`：文件列表
- `DELETE /api/files`：删除文件
- `GET /api/source`：打开来源文件
- `GET /api/health`：健康检查

### 7.2 登录页与问答页

前端模板位于：

- `course_rag/templates/auth.html`
- `course_rag/templates/dashboard.html`

前端脚本与样式位于：

- `course_rag/static/js/auth.js`
- `course_rag/static/js/app.js`
- `course_rag/static/css/styles.css`

当前界面实现了：

- 登录页状态提示
- 登录页仅保留登录，不向终端用户开放自助注册
- 问答页对话式布局
- 启动阶段遮罩与索引提示
- 历史记录卡片列表
- 文件抽屉面板
- 自定义删除确认层

### 7.3 当前前端体验

前端当前已经与索引状态联动：

- 登录页在索引中会禁用登录按钮并提示等待
- 主页面在索引中会禁用输入框并显示构建遮罩
- 索引完成后自动恢复可交互状态

---

## 8. 多用户隔离与 MySQL 持久化

### 8.1 用户隔离

系统会为每个用户创建独立资料目录：

```text
storage/materials/<username>/
```

登录后问答不再使用统一公共目录，而是切换到当前用户自己的资料目录。因此：

- 用户上传的文件仅自己可见
- 不同用户即使问同样的问题，答案也可能不同
- 资料目录内容直接影响检索效果

需要说明的是，公共目录 `data/course/` 仍然存在，但它主要用于未登录阶段的默认上下文展示。真正进入系统后，问答服务和文件面板都只面向当前登录用户的私有资料目录。

### 8.2 持久化设计

MySQL 存储模块位于 `course_rag/persistence/store.py`。当前数据库 `course_rag` 中主要包含：

- `users`
- `history`
- `user_materials`

其职责分别是：

- `users`：保存用户信息与密码哈希
- `history`：保存每次提问、回答、模式和来源
- `user_materials`：保存用户资料元数据

这种设计使系统在服务重启后仍能保留用户与使用记录。

---

## 9. 部署与工程化支持

### 9.1 本地运行

本地运行方式如下：

```bash
python -m pip install -r requirements.txt
python app.py
```

默认访问地址：

```text
http://127.0.0.1:7860
```

### 9.2 部署文件

项目已经补齐以下部署文件：

- `Dockerfile`
- `gunicorn.conf.py`
- `deploy/1panel/docker-compose.yml`
- `deploy/1panel/.env.example`
- `deploy/1panel/README.md`

### 9.3 1Panel 部署链路

服务器部署流程如下：

1. 上传项目到服务器
2. 通过 1Panel 编排启动应用容器与 MySQL 容器
3. 使用 Gunicorn 提供应用服务
4. 用 1Panel 网站模块创建反向代理
5. 将外部流量代理到本地应用端口

默认映射为：

```text
127.0.0.1:17860 -> 7860
```

### 9.4 部署阶段的典型问题

在项目从本地运行迁移到服务器过程中，曾处理过以下问题：

- MySQL 8 认证插件与 Python 依赖不兼容
- embedding 接口批量大小与服务端限制不一致
- 站点目录与项目源码目录混用导致路径混乱
- 远程模型 key 未配置导致回答模式回退
- 用户资料目录不存在导致登录后 500 错误

这些问题表明，RAG 系统的落地效果不仅取决于算法，也高度依赖路径管理、环境配置、依赖安装和部署细节。

---

## 10. 系统效果与分析

### 10.1 当前默认知识库规模

在默认公共资料目录下，系统当前会构建：

- `10` 份 Markdown 课程资料
- `215` 个检索切片

但这一数值仅代表未登录状态下的公共索引。用户登录后，`documents` 与 `chunks` 会切换为当前用户私有资料目录的统计结果，因此不同用户之间不一定一致。

### 10.2 当前能力表现

从当前实现看，系统已经具备以下效果：

- 对课程安排、概念解释、章节总结等问题可进行检索增强回答
- 对关键词明确的问题，BM25 召回较稳定
- 对语义改写问题，embedding 召回可补足 BM25 的不足
- 通过 Hybrid Retrieval，整体召回鲁棒性优于纯 BM25

### 10.3 当前不足

虽然检索能力已提升，但仍存在以下限制：

- embedding 向量没有持久化保存
- 服务重启时需要重新全量向量化
- 启动时间受语料规模和远程接口延迟影响明显
- 当前尚无独立向量数据库支撑更大规模检索
- 自动化测试覆盖仍然不足

---

## 11. 项目亮点

本项目的主要亮点包括：

1. 已从纯关键词检索升级到 Hybrid Retrieval。  
2. 已真正接入 embedding 检索，而不仅是预留配置。  
3. 启动阶段实现了异步索引与前端提示联动。  
4. 多用户资料目录与历史记录隔离明确。  
5. 支持远程模型生成与本地回退。  
6. 已适配 Docker、Gunicorn 与 1Panel 部署。  
7. 整体形成了从资料、检索、生成、前端、数据库到部署的完整系统链路。  

---

## 12. 后续改进方向

后续可以从以下方向继续优化：

1. 接入持久化向量数据库  
   如 Chroma、FAISS 或 pgvector，避免每次重启重算 embedding。

2. 增量索引机制  
   仅为新增或变更文件重算向量，减少构建耗时。

3. 增加 rerank 层  
   在 BM25 + embedding 召回后进一步做精排。

4. 完善管理员能力  
   支持用户管理、批量资料导入和后台统计。

5. 增加自动化测试  
   覆盖检索、接口、持久化和部署链路。

6. 扩展更多资料格式  
   在 Markdown 之外更稳定地支持 PDF、DOCX 等课程文件。

---

## 13. 结论

本项目已经从一个课程资料问答原型发展为一个具备完整工程链路的课程问答系统。与早期版本相比，当前实现的关键提升在于：检索后端已经由单一 BM25 升级为 Hybrid Retrieval，embedding 检索已经真正落地，启动阶段也通过异步索引与前端状态提示得到了工程优化。

从课程项目视角看，这个系统不仅展示了 RAG 的基础思想，还体现了一个真实问答系统在多用户、持久化、文件管理、部署与运行优化等方面的工程复杂度。虽然当前还没有引入持久化向量数据库，但系统已经为后续继续演进打下了明确而可用的基础。

---

## 参考文件

本报告主要基于以下项目文件整理：

- `README.md`
- `config/rag.yml`
- `config/chroma.yml`
- `course_rag/web.py`
- `course_rag/core/config_handler.py`
- `course_rag/persistence/store.py`
- `course_rag/services/rag_retriever.py`
- `course_rag/services/rag_service.py`
- `course_rag/services/rag_generator.py`
- `course_rag/static/js/app.js`
- `course_rag/static/js/auth.js`
- `course_rag/templates/auth.html`
- `course_rag/templates/dashboard.html`
- `deploy/1panel/docker-compose.yml`
