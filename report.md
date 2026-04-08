# COMP5575 Course RAG

## 课程项目报告

**课程名称：** COMP5575 High-Dimensional Data Management and Analytics  
**项目名称：** Course RAG: 基于课程资料的检索增强问答系统  
**项目类型：** 课程项目 / 系统实现报告  
**提交形式：** Markdown 项目报告  

---

## 摘要

本项目围绕课程讲义、课堂笔记和参考资料，设计并实现了一个面向课程场景的检索增强问答系统。系统以 Markdown 课程资料为核心知识源，当前采用本地 BM25 风格检索器完成资料召回，同时在配置层预留了基于 embedding 的向量化扩展能力，用于后续接入语义检索。在生成阶段，系统支持两种回答模式：一是通过 OpenAI 兼容接口调用远程大模型进行生成，二是在远程模型不可用时回退到本地摘要模式，从而保证系统在不同运行环境下都具备基本可用性。为了满足实际使用需求，项目进一步实现了 Web 交互界面、多用户登录、用户级资料隔离、历史记录管理、文件上传与删除、MySQL 持久化以及 1Panel 容器化部署支持。

从工程实现角度看，本项目不仅完成了课程问答原型的构建，还覆盖了从数据组织、检索与生成逻辑、前后端交互、数据库设计，到部署上线的完整链路。系统当前已经能够支持用户围绕课程资料进行基于证据的提问，并以可解释的方式返回答案和来源信息。报告重点讨论了课程资料在 RAG 场景中的向量化思路，包括文档切块、embedding 表示、相似度计算、向量召回与语义增强路径；同时也明确指出，当前运行版本仍以 BM25 基线为主，embedding 向量检索尚处于预留与可扩展阶段。尽管远程模型状态展示和自动化测试体系仍有优化空间，但项目已经较完整地体现了 RAG 系统在课程资料场景中的落地过程，并具备继续扩展为更强语义检索系统的基础。

## 关键词

RAG；课程资料问答；文本向量化；Embedding；BM25 检索；多用户资料隔离；MySQL 持久化

---

## 1. 引言

### 1.1 研究背景

随着大语言模型能力的持续提升，基于自然语言的问题回答系统已经能够较好地完成开放域对话和文本生成任务。然而，在课程问答、知识问答、企业文档问答等需要“依据已有资料回答”的场景中，单纯依赖大模型自身参数往往会带来事实偏差、内容幻觉和不可追溯等问题。因此，将外部知识检索与大模型生成结合起来的 Retrieval-Augmented Generation, RAG，成为一种兼顾灵活性与可靠性的常见技术路线。

在课程场景中，学生常常需要围绕讲义、课堂笔记和课程说明提问，例如课程安排、算法定义、公式解释、章节重点和考试范围等。如果能够构建一个专门面向课程资料的问答系统，用户便可以通过自然语言快速定位相关内容，而不必手动翻阅大量材料。这类系统既具备明确的应用价值，也能够作为 RAG 课程项目的一个合适落地场景。

### 1.2 项目目标

本项目旨在实现一个面向课程资料的轻量级 RAG Web 系统，具体目标如下：

- 构建一个围绕课程讲义和笔记的课程问答系统，而不是通用闲聊机器人。
- 实现基于本地文本资料的检索增强问答流程，并为 embedding 向量检索预留清晰扩展路径。
- 支持 OpenAI 兼容接口的远程大模型生成，并保留本地摘要回退能力。
- 提供完整的 Web 使用界面，包括登录、提问、历史查看和文件管理。
- 支持多用户资料隔离，使不同用户拥有独立的知识库。
- 将用户、历史记录和资料元数据持久化到 MySQL 中。
- 支持通过 Docker 和 1Panel 完成服务器部署。

### 1.3 报告结构

本报告首先介绍项目需求与总体设计，然后说明核心实现模块，包括配置、检索、生成、持久化和前端交互；随后总结项目的数据组织方式、部署方案与运行效果；最后给出项目亮点、局限和后续改进方向。

---

## 2. 需求分析

### 2.1 功能需求

结合课程场景，本项目需要满足以下功能需求：

1. 用户登录  
   系统需要支持账号登录，并通过会话维持登录状态。

2. 课程问答  
   用户输入自然语言问题后，系统需要围绕课程资料返回回答。

3. 资料检索  
   回答必须尽量基于已有讲义、笔记和参考资料，而不是无依据生成。

4. 用户资料隔离  
   不同用户上传的资料应互相独立，不能共用同一知识库目录。

5. 历史记录管理  
   系统应保存每个用户的提问历史，并允许用户查看和删除。

6. 文件管理  
   用户应能够查看自己的课程资料文件，支持上传、打开和删除。

7. 后端持久化  
   用户、历史记录和资料元数据不应随服务重启而丢失。

8. 可部署性  
   系统需要支持在服务器环境中部署，并具备可持续运行能力。

### 2.2 非功能需求

- 可维护性：模块划分清晰，配置、业务逻辑和持久化分离。
- 可扩展性：后续可以替换更强的检索器或接入向量数据库。
- 可用性：前端界面应简洁直观，适合问答场景使用。
- 稳定性：远程模型不可用时，系统不应完全失效。
- 可移植性：支持本地运行和服务器容器化部署。

---

## 3. 总体设计

### 3.1 系统总体架构

本项目采用分层设计，整体可划分为四层：

1. 表现层  
   由 Flask 模板和前端脚本构成，负责页面展示、用户交互和 API 调用。

2. 业务层  
   由 RAG 服务模块组成，负责文档切块、检索、生成和用户索引管理。

3. 持久化层  
   由 MySQL 存储模块构成，负责用户、历史记录和资料元数据的读写。

4. 基础设施层  
   由配置、日志、路径与文件处理模块构成，为系统运行提供支撑。

从数据流角度看，系统的核心处理流程如下：

1. 用户登录系统。
2. 系统为当前用户定位其独立资料目录。
3. 用户提问后，检索器在用户资料目录建立的索引中召回相关片段。
4. 生成器基于检索结果组织回答。
5. 回答和来源写入历史记录。
6. 用户可继续查看来源、管理文件和回看历史。

### 3.2 项目目录结构

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

### 3.3 核心设计原则

本项目在设计时遵循以下原则：

- 资料优先：所有回答必须尽量基于已检索到的课程资料。
- 用户隔离：每个用户拥有独立资料目录和历史记录。
- 轻量可运行：先构建可靠的文本检索基线，再逐步增强。
- 部署友好：尽量降低服务器运行依赖，适配 Docker 和 1Panel。

---

## 4. 系统实现

### 4.1 配置管理

配置逻辑位于 [config_handler.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/core/config_handler.py)。

系统采用 YAML 配置文件与本地环境文件结合的方式：

- `config/rag.yml`  
  定义应用名、公共资料目录、用户资料目录、允许文件类型等。

- `config/agent.yml`  
  定义远程模型是否启用、基础地址、模型名和超参数。

- `config/prompts.yml`  
  定义系统提示词、用户提示模板和推荐问题。

- `.env.local`  
  用于本地存储 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 MySQL 连接信息。

当前关键配置如下：

- 应用名：`COMP5575 Course RAG`
- 公共课程目录：`data/course`
- 用户资料根目录：`storage/materials`
- 默认允许类型：`.md`
- 远程模型名：`qwen3-max`
- 远程接口地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`

### 4.2 文档加载与切块

资料加载位于 [file_handler.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/core/file_handler.py)，切块逻辑位于 [rag_chunking.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_chunking.py)。

系统当前默认使用 Markdown 资料，其原因是：

- 文本结构清晰，标题、列表和段落层级较容易保留；
- 比 PDF 更少出现文本抽取噪声；
- 更适合课程项目中对可控性和稳定性的要求。

索引建立流程如下：

1. 扫描资料目录中符合扩展名要求的文件。
2. 读取文件内容并构建文档对象。
3. 按固定长度和重叠窗口进行切块。
4. 将所有 chunk 交给检索器建立索引。

当前检索参数包括：

- `chunk_size = 420`
- `chunk_overlap = 80`
- `top_k = 4`
- `max_context_chars = 2200`
- `min_score = 0.1`
- `title_boost = 0.45`

### 4.3 向量化设计与检索策略

向量化是 RAG 系统中的关键环节，其目标是把非结构化文本转换为可计算的数值表示，使系统能够根据语义相似度而不仅仅是关键词重合度进行检索。对于课程资料问答场景，向量化的意义主要体现在以下几个方面：

- 能够更好地处理“同义表达”问题，例如“上课时间”“课程安排”“lecture schedule”可能指向同一类知识。
- 能够降低纯词面匹配的局限，使系统在课程概念、公式解释和章节总结场景中具有更好的语义泛化能力。
- 为后续接入向量数据库、混合检索和 rerank 提供统一的数据表示基础。

当前仓库的配置层已经预留了 embedding 模型字段：

- `config/rag.yml` 中包含 `embedding_model_name: text-embedding-v4`

这说明系统设计时已经考虑了向量化路线，只是当前运行版本尚未将其完整落地为在线检索链路。

#### 4.3.1 文档向量化的基本流程

在课程资料场景中，文档向量化通常包含以下步骤：

1. 文档清洗  
   对 Markdown、PDF 或笔记文本进行标准化处理，去除无关符号、格式噪声和空白片段。

2. 文档切块  
   将完整文档按段落、标题层级或固定窗口切分为多个 chunk。切块过大容易引入噪声，过小则会破坏语义完整性，因此需要在语义完整性和检索粒度之间取得平衡。

3. Chunk 编码  
   使用 embedding 模型将每个 chunk 编码为固定维度的向量。例如，一个 chunk 可以被表示为一个高维实数向量：

   \[
   \mathbf{v}_i \in \mathbb{R}^d
   \]

4. 向量存储  
   将每个 chunk 的文本、元数据和向量一并保存到向量数据库或本地索引结构中，便于后续查询。

对于本项目而言，文档切块已经在 [rag_chunking.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_chunking.py) 中实现。若后续接入 embedding，只需要在切块完成后，增加“chunk -> embedding 向量”的编码步骤即可。

#### 4.3.2 查询向量化

与文档向量化相对应，用户问题也需要被编码为与文档向量同一语义空间中的向量：

\[
\mathbf{q} \in \mathbb{R}^d
\]

这样，系统就可以直接比较问题向量与各个文档向量之间的相似度，从而实现语义检索。

在课程问答场景中，这一点尤其重要。例如用户问：

- “什么时候上课”
- “课程安排是什么”
- “lecture 是几点开始”

这三种问法在词面上差异较大，但从语义上都指向课程时间安排。若采用向量化表示，系统会更容易把这些问法映射到相近的语义空间区域。

#### 4.3.3 相似度计算

向量检索中最常用的相似度度量之一是余弦相似度：

\[
\text{cos}(\theta) = \frac{\mathbf{q} \cdot \mathbf{v}_i}{\|\mathbf{q}\|\|\mathbf{v}_i\|}
\]

其中：

- \(\mathbf{q}\) 表示问题向量
- \(\mathbf{v}_i\) 表示第 \(i\) 个文档块的向量
- 分子表示点积
- 分母表示向量范数的乘积

余弦相似度的优点在于，它更关注方向而不是长度，因此特别适合文本检索场景。不同 chunk 的长度可能不同，但在 embedding 空间中，方向更能体现语义内容。

#### 4.3.4 向量化在本项目中的理想链路

如果将本项目从当前的 BM25 检索升级为基于 embedding 的语义检索，其理想流程可设计为：

1. 读取课程资料  
2. 执行文档切块  
3. 为每个 chunk 生成 embedding 向量  
4. 将向量和 chunk 元数据写入向量索引  
5. 用户提问时，先将问题编码为向量  
6. 计算问题向量与 chunk 向量之间的相似度  
7. 召回 Top-K 最相关 chunk  
8. 将召回结果交给远程大模型或本地摘要器生成答案

这一流程相比当前词项匹配检索，最大的增强点在于：系统能够围绕“语义相似”而不仅是“词项重合”召回资料。

#### 4.3.5 当前实现与预留扩展

需要明确指出的是，当前代码实际运行时，检索后端仍为：

```text
backend: local_bm25
```

也就是说，当前系统的在线召回链路仍然基于词项统计，而不是真正的 embedding 向量检索。对应实现位于 [rag_retriever.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_retriever.py)，其中通过分词、词频、逆文档频率和标题加权来完成排序。

因此，本项目在“向量化”方面目前处于以下状态：

- 设计层：已经明确了 embedding 扩展方向；
- 配置层：已经预留 embedding 模型名称；
- 数据层：已经完成 chunk 化和元数据组织；
- 运行层：尚未把向量编码和向量相似度召回接入主链路。

从课程项目报告角度看，这一状态是合理的。因为它展示了一个完整的工程演进路径：先用 BM25 构建稳定基线，再在此基础上逐步替换为语义向量检索。

### 4.4 当前检索模块实现

检索逻辑位于 [rag_retriever.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_retriever.py)。

当前版本采用本地 BM25 风格检索器，而不是向量数据库，主要考虑如下：

- 实现成本较低，便于快速搭建课程项目原型。
- 对课程 Markdown 资料场景具有较好的词项匹配效果。
- 不依赖额外服务，便于本地运行和服务器部署。

BM25 检索器当前主要完成以下工作：

- 对中英文文本进行轻量分词；
- 计算词频和逆文档频率；
- 对标题命中和章节标题命中进行额外加权；
- 根据得分返回 Top-K 相关 chunk。

这使系统即使在没有 embedding 和向量库的情况下，也能形成一个可运行的课程问答基线。

### 4.5 生成模块

生成逻辑位于 [rag_generator.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_generator.py)。

当前系统支持三种回答模式：

1. `remote_llm`  
   当远程模型启用且可成功读取 `OPENAI_API_KEY` 时，系统调用 OpenAI 兼容接口生成回答。

2. `local_summary`  
   当远程模型不可用或请求失败时，系统根据检索到的句子进行本地摘要和组织。

3. `no_context`  
   当知识库中没有足够相关的资料时，系统明确说明资料不足。

这种设计使系统具有较好的鲁棒性。即使服务端未正确配置远程模型，系统仍然可以作为“检索 + 本地摘要”工具继续运行。

### 4.6 Web 后端实现

Web 路由位于 [web.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/web.py)。

当前主要接口如下：

- `GET /`：问答主页
- `GET /login`：登录页
- `POST /api/auth/login`：登录接口
- `POST /api/auth/logout`：退出接口
- `GET /api/auth/me`：查询登录态
- `POST /api/ask`：提问接口
- `GET /api/history`：读取历史记录
- `DELETE /api/history/<record_id>`：删除历史记录
- `POST /api/upload`：上传资料
- `GET /api/files`：列出资料文件
- `DELETE /api/files`：删除资料文件
- `GET /api/source`：打开来源文件
- `GET /api/health`：健康检查

### 4.7 用户体系与 MySQL 持久化

数据持久化位于 [store.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/persistence/store.py)。

系统启动时会自动：

- 初始化 `storage/` 目录；
- 创建 MySQL 数据库 `course_rag`；
- 创建 `users`、`history` 和 `user_materials` 三张核心表；
- 迁移旧版 JSON 数据；
- 为用户建立资料目录。

其中：

- `users` 表保存用户名、密码哈希和创建时间；
- `history` 表保存提问、回答、模式和来源；
- `user_materials` 表保存用户资料文件的元数据。

密码采用哈希形式保存，而不是明文保存，提高了系统的基本安全性。

### 4.8 多用户资料隔离

用户级 RAG 服务管理位于 [rag_service.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_service.py)。

系统登录后，并不会继续使用公共 `data/course` 目录回答问题，而是切换到：

```text
storage/materials/<username>/
```

这意味着：

- 用户上传的文件只对自己可见；
- 不同用户的检索结果彼此隔离；
- 相同问题在不同用户下可能得到不同答案；
- 公共课程资料与用户私有知识库是两套概念。

这一点也是系统从单用户原型向多用户系统演进的关键。

---

## 5. 前端设计与交互实现

前端模板位于：

- [auth.html](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/templates/auth.html)
- [dashboard.html](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/templates/dashboard.html)

前端资源位于：

- [styles.css](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/static/css/styles.css)
- [app.js](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/static/js/app.js)
- [auth.js](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/static/js/auth.js)

### 5.1 登录页设计

登录页面面向普通用户，仅保留必要内容：

- 系统名称
- 简短功能说明
- 用户名输入框
- 密码输入框
- 登录按钮

考虑到系统采用管理员控用户的方式，前端自助注册功能已关闭。

### 5.2 问答页设计

问答页采用现代浅色工作台风格，尽量接近对话式产品的使用习惯，页面中集成了：

- 当前用户展示
- 退出登录
- 问答输入框
- 回答展示区
- 历史记录区
- 文件查看与管理区

### 5.3 历史记录管理

历史记录区支持：

- 仅显示当前用户自己的历史；
- 固定卡片高度；
- 超出部分省略号显示；
- 删除单条历史；
- 使用页面内自定义确认弹层，而不是浏览器原生提示框。

### 5.4 文件面板

文件面板支持：

- 查看当前资料文件列表；
- 显示文件类型、名称、大小和更新时间；
- 打开文件；
- 删除文件；
- 上传新文件后自动刷新知识库。

---

## 6. 数据组织与运行状态

### 6.1 默认公共数据集

当前 `data/course` 下包含 10 份 Markdown 课程资料：

- `Lecture 1.md`
- `Lecture 2.md`
- `Lecture 3.md`
- `Lecture 4.md`
- `Lecture 5.md`
- `Lecture 7.md`
- `Lecture 8.md`
- `Lecture 9.md`
- `Lecture 11.md`
- `Note.md`

在当前切块参数下，默认公共知识库通常可构建约 215 个检索片段。

### 6.2 用户资料目录

除公共资料外，系统还支持用户私有资料目录：

```text
storage/materials/lyy/
storage/materials/zzw/
...
```

用户登录后，问答逻辑会优先使用自己的私有资料目录建立索引。因此，若服务器和本地的用户资料目录不同，即使提问相同，回答也可能不同。

### 6.3 运行模式差异

在系统实际运行中，回答模式通常会表现为：

- `remote_llm`
- `local_summary`
- `no_context`

其中，若服务端只显示“远程模型已启用”但未实际配置 `OPENAI_API_KEY`，则后端仍会回退到本地模式。这是部署阶段一个非常重要的工程细节。

---

## 7. 部署实现与工程化支持

### 7.1 本地运行

本地运行方式如下：

```bash
python -m pip install -r requirements.txt
python app.py
```

应用默认监听：

```text
http://127.0.0.1:7860
```

### 7.2 生产部署组件

项目已经补齐部署相关文件：

- [Dockerfile](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/Dockerfile)
- [gunicorn.conf.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/gunicorn.conf.py)
- [deploy/1panel/docker-compose.yml](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/deploy/1panel/docker-compose.yml)
- [deploy/1panel/README.md](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/deploy/1panel/README.md)

依赖文件 [requirements.txt](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/requirements.txt) 当前包含：

- Flask
- PyYAML
- requests
- pypdf
- PyMySQL
- gunicorn
- cryptography

### 7.3 1Panel 部署流程

系统采用 Docker Compose 启动应用容器和 MySQL 容器，随后通过 1Panel 的反向代理网站进行外部访问。

部署基本流程为：

1. 上传项目到服务器；
2. 配置 `.env` 文件；
3. 使用 1Panel 编排启动容器；
4. 通过 Gunicorn 提供应用服务；
5. 使用 1Panel 网站模块创建反向代理；
6. 将外部请求转发到本地服务端口。

当前默认映射为：

```text
127.0.0.1:17860 -> 7860
```

### 7.4 部署阶段遇到的问题

项目在服务器部署过程中，已经处理过以下典型问题：

- Python 版本差异带来的兼容性问题；
- MySQL 8 认证插件与 `cryptography` 依赖问题；
- 1Panel 中构建上下文路径解析问题；
- 登录后用户私有资料目录不存在导致的 500 错误；
- 站点目录与项目源码目录混用导致的路径混淆问题；
- 服务端未配置大模型 key 导致回答模式退回本地摘要的问题。

这些问题表明，RAG 系统从本地实验原型走向服务器环境时，需要额外处理目录挂载、环境变量、依赖安装、数据库初始化和反向代理配置等工程细节。

---

## 8. 系统测试与效果分析

### 8.1 功能验证

从当前项目实现和实际运行结果看，以下功能已经完成：

- 用户登录
- 登录态维持
- 问答接口调用
- 历史记录保存与删除
- 用户资料上传
- 文件列表查看
- 文件删除与索引刷新
- MySQL 持久化
- 1Panel 反向代理访问

### 8.2 运行效果

项目本地运行时，在远程模型 key 正确配置的前提下，可以返回 `remote_llm` 模式的答案，回答通常更完整、更自然。服务器运行时，若未配置 key，则会回退到 `local_summary` 或 `no_context`，这会导致同样问题在本地和服务器上出现回答不一致。

从检索层面看，当前系统的回答质量仍显著受到 BM25 词项匹配能力的限制。对于“课程时间”“考试安排”“章节总结”这类关键词明确的问题，系统通常能够较稳定召回相关内容；但对于“换一种问法”“跨语言表达”“较强语义改写”的问题，BM25 的鲁棒性弱于基于 embedding 的向量检索。因此，若项目后续希望进一步提升复杂问法下的召回率，最直接的方向就是把当前 chunk 索引升级为向量索引。

因此，系统的最终回答质量主要受两个因素影响：

1. 当前用户资料目录中的内容是否完整；
2. 服务端是否真正配置并调用了远程大模型。

### 8.3 工程经验总结

本项目的实现说明，一个 RAG 系统的效果不仅取决于算法本身，还强烈依赖于工程实现的完整性。即使本地功能已经可用，若服务器端环境变量、数据目录、依赖或部署路径未配置正确，系统也可能表现出明显不同的行为。

---

## 9. 项目亮点

本项目的亮点主要体现在以下几个方面：

1. 场景聚焦清晰  
   项目专门围绕课程资料问答，目标明确，数据来源稳定。

2. 架构层次清晰  
   配置、业务逻辑、持久化和前端交互分层明确。

3. 多用户隔离  
   资料目录和历史记录按用户隔离，具备平台化基础。

4. 支持回退  
   即使远程模型不可用，仍可以本地摘要模式继续工作。

5. 工程闭环完整  
   从资料管理、检索、生成到数据库与部署，形成了完整系统链路。

6. 部署落地性较强  
   项目不仅能本地运行，还已经适配 Docker、Gunicorn 和 1Panel。

---

## 10. 局限性与改进方向

### 10.1 当前局限

尽管项目已具备完整原型能力，但仍存在以下局限：

- 检索阶段仍是轻量 BM25 基线，语义理解能力有限；
- UI 中远程模型状态展示与实际可用性未完全解耦；
- 多环境配置管理还不够统一；
- 自动化测试覆盖不足；
- 对 PDF、DOCX 等非 Markdown 资料类型支持有限。

### 10.2 后续改进方向

后续可考虑从以下方向继续扩展：

1. 引入 embedding 与向量数据库  
   使用 `text-embedding-v4` 等模型将 chunk 和 query 编码为统一向量空间中的表示，并以余弦相似度完成 Top-K 召回。

2. 引入混合检索  
   将当前 BM25 与向量检索并行召回，再进行融合排序，以兼顾关键词命中和语义相似。

3. 增加模型状态探测  
   区分“配置启用”和“运行可用”。

4. 增强管理员功能  
   支持用户管理、批量导入资料和后台统计。

5. 完善测试体系  
   增加单元测试、接口测试和部署验证。

6. 支持更多文件类型  
   优化 PDF、DOCX 的文本抽取与切块。

7. 增加向量缓存与离线建索引流程  
   避免每次重启时重复计算 embedding，提升部署和重建索引效率。

8. 规范部署目录结构  
   进一步解耦源码目录、站点目录和持久化目录。

---


## 11. 结论

本项目已经完成了一个面向课程资料的 RAG Web 系统，从最初的数据组织和检索增强回答原型，逐步扩展为一个支持多用户、文件管理、数据库持久化和服务器部署的完整工程系统。项目较好地体现了 RAG 技术在课程资料问答场景中的实际落地方式，也展示了从算法原型到部署上线之间需要解决的大量工程问题。

从课程项目角度看，该系统已经具备较完整的教学展示价值和报告总结价值。它不仅说明了如何构建“检索 + 生成”的问答流程，也体现了在真实环境中处理用户隔离、状态持久化、部署适配和运行稳定性问题的能力。后续若进一步引入向量检索和更完善的模型状态管理，系统还可以继续发展为更强的课程知识问答平台。

---

## 参考文件

本报告主要依据以下项目文件整理：

- [README.md](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/README.md)
- [config/rag.yml](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/config/rag.yml)
- [config/agent.yml](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/config/agent.yml)
- [config/prompts.yml](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/config/prompts.yml)
- [course_rag/web.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/web.py)
- [course_rag/core/config_handler.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/core/config_handler.py)
- [course_rag/persistence/store.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/persistence/store.py)
- [course_rag/services/rag_service.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_service.py)
- [course_rag/services/rag_generator.py](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/course_rag/services/rag_generator.py)
- [deploy/1panel/docker-compose.yml](/E:/Academic/COMP5575_High-Dimensional_Data_Management_and_Analytics/Project/RAG/deploy/1panel/docker-compose.yml)
