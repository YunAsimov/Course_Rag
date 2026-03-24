### 📚 知识库基础 (Knowledge Base Preliminary) 深度详解

#### 1. 核心定义与存在意义 (Definition & Why)

**Q: 什么是知识库 (KB)?**

- 知识库是一个旨在存储、组织和检索信息的系统。
- **结构**: 核心单元是 **三元组 (Triples)**，即 `<Subject, Relation, Object>` (例如 `<John Lennon, MemberOf, Beatles>`)。

**Q: 为什么要用知识库 (Why not Relational Database)?**

1. **非结构化数据处理**: 关系型数据库 (RDB) 难以有效处理非结构化数据（如大段文本），而 KB 可以提取其中的实体和关系。
2. **推理能力 (Inference)**:
    - **RDB**: 存储的是死数据 (Table)。
    - **KB**: 存储的是**语义 (Semantics)**。
    - _例子_: 如果数据库存了 "Eva married Adam"，RDB 很难直接回答 "Who is Eva's husband?"（除非专门写查询）。但 KB 可以通过逻辑推理出 `<Adam, HusbandOf, Eva>`。
3. **复杂关系**: KB 的图结构能自然地表示实体间复杂的互联关系。

#### 2. 知识库的三大分类 (The 3 Dimensions/Types) 🔥

##### ① 基于文本的知识库 (Text-based Knowledge Base)

这是最传统、最基础的类型。

- **定义**: 主要以**文本格式**存储和组织信息的系统。
- **数据形态**: 结构化的文本三元组 `<Subject, Relation, Object>`。
- **特点**:
    - **集成性**: 容易与外部数据库、API 或工具连接，用于丰富数据访问。
    - _例子_: Wikidata, Freebase。

##### ② 多模态知识库 (Multi-modal Knowledge Base)

这是当前 AI 的热点，解决了文本“不仅要读，还要看”的问题。

- **定义**: 集成了多种数据类型（不仅是文本）的知识库。
- **涵盖模态**:
    - **图像 (Image)**
    - **图表 (Graphs)**
    - **表格 (Tables)**
- **核心价值**:
    - **更丰富的关系**: 促进了实体间复杂关系的建立（例如，将 "John Lennon" 的文本节点链接到他的 "照片" 节点）。
    - **全面检索**: 支持跨模态的信息检索和分析。

##### ③ 主观知识库 (Subjective Knowledge Base) 🔥 (特色考点)

这是很多传统教材不涉及，但这门课特别强调的**第三个维度**：从**客观事实**转向**主观认知**。

- **定义**: 一个捕捉和组织基于**个人观点 (Personal Opinions)**、**信仰 (Beliefs)**、**经验 (Experiences)** 和 **解读 (Interpretations)** 的系统，而不是仅存储客观事实。
- **对比 (Contrast)**:
    - **客观 KB (Objective)**: `<Liverpool, IsA, City>` —— 这是不可争辩的事实。
    - **主观 KB (Subjective)**: `<Liverpool, IsA, Safe City>` —— 这是一个观点，对于不同人可能不同。
- **输入来源**: 现有的 KB + **众包评论 (Crowd Comments)**。
- **核心应用**:
    - **个性化 (Personalization)**: 能够捕捉主观属性，从而返回最符合**用户个性化需求 (User Need)** 的结果。
    - _例子_: 用户搜索 "Popular band"（主观），KB 返回 "Beatles"；用户搜索 "Safe city"（主观），KB 返回 "Liverpool"。

### 🏗️ 知识库构建全流程 (The Pipeline)

构建知识库的目标是将**非结构化**的文本输入，转化为**结构化**的三元组输出。

流程总览：

**Data Collection $\rightarrow$ Entity Extraction $\rightarrow$ Resolution & Linking $\rightarrow$ Relation Extraction $\rightarrow$ Updating/Fusion**

#### 1. 数据收集 (Data Collection)

- **输入**: 非结构化文本语料库 (Unstructured text corpus)，包含字符串、链接、混乱的文本。
- **挑战**: 原始数据通常是混乱且无逻辑的 (Chaotic, unstructured, and irrational)，目标是将其转化为预期的、结构化的数据。

#### 2. 实体抽取与类型化 (Entity Extraction & Typing)

这一步的目的是“认出谁是谁”。

- **A. 词性标注 (Part-of-Speech / POS Tagging)**
    - **作用**: 识别句子中的名词、动词、形容词等。
    - **目的**: 消除词义歧义。例如 "Lead" 既可以是动词（领导），也可以是名词（铅）。POS Tagging 可以帮助区分它们。
- **B. 命名实体识别 (Named Entity Recognition, NER)**
    - **定义**: 识别文本中具有特定意义的实体边界和类别（如人名、地名、组织）。
    - **方法**:
        - **基于规则 (Rule-based)**: 依赖人工定义的规则（如正则表达式）。准确但难以扩展。
        - **随机/概率模型 (Stochastic/Probabilistic)**: 使用统计模型（如 CRF, BERT）自动学习。
- **C. 实体类型化 (Entity Typing)**
    - **粗粒度 (Coarse-grained)**: 也就是 NER 的基础分类 (Person, Location, Organization)。
    - **细粒度 (Fine-grained)**: 提供更具体的层级信息 (e.g., Artist, Politician, Scientist)。

#### 3. 实体解析与链接 (Entity Resolution & Linking) 🔥 (易混淆考点)

这一步的目的是“清洗”和“对齐”。

- **A. 实体解析 (Entity Resolution / Entity Matching)**
    - **解决问题**: **同一性问题 (Identity Problem)**。即确认多条不同的记录（如 "J. Lennon" 和 "John Winston Lennon"）是否指向现实世界中的**同一个**实体。
    - **标准流程**:
        
        1. **Blocking (分块)**: 将可能匹配的记录分到一组，减少比较次数。
        2. **Block Processing**: 处理块内数据。
        3. **Entity Matching**: 计算相似度。
        4. **Clustering**: 将匹配的记录聚类合并。
            
- **B. 实体链接 (Entity Linking / Disambiguation)**
    - **解决问题**: **歧义问题 (Ambiguity Problem)**。即文本中的某个提及 (Mention) 到底是指知识库中的哪一个实体。
    - **例子**: 文本中提到 "Paris"。
        - 是指 "Paris (City in France)"？
        - 还是指 "Paris Hilton (Person)"？
    - **方法**: 利用上下文 (Context) 将文本中的 "Paris" 链接到 KB 中的唯一 ID。

#### 4. 关系抽取 (Relation Extraction) 🔥 (核心/必考)

目的是从文本中提取语义关系，形成 `<Subject, Predicate, Object>`。

- **抽取范式 (Extraction Paradigms)**:
    - **Pipeline**: 先做实体抽取，再做关系分类。_缺点_: 误差传播 (Error Propagation)。
    - **Joint Learning**: 实体和关系同时抽取，互相辅助。
- **关键对比: Closed IE vs. Open IE** (请务必抄在笔记上)

|**特性**|**Closed IE (封闭式抽取)**|**Open IE (开放式抽取)**|
|---|---|---|
|**定义**|提取**预定义 (Pre-specified)** 的特定关系|提取文本中出现的**任意**动词短语作为关系|
|**关系集**|固定 (Fixed)，如 `born_in`, `spouse_of`|开放 (Open)，不限数量|
|**输入要求**|需要**标注数据 (Labeled Data)**|不需要 (Unsupervised) 或仅需少量|
|**准确率**|**高 (Accurate)**，粒度精细|较低，容易产生噪音和冗余|
|**PPT 例子**|`<John, born_in, Liverpool>`|`<John, was born in, Liverpool>`|
|**优缺点**|优点: 准确; 缺点: 需要大量人工标注|优点: 自动化, 覆盖广; 缺点: 精度低|

#### 5. 知识库更新/数据融合 (KB Updating / Data Fusion)

当多个来源提供关于同一实体的信息时（可能有冲突），如何合并？

- **冲突检测 (Conflict Detection)**: 发现不同来源的数据不一致（如 Source A 说身高 180，Source B 说 175）。
- **真值发现 (Truth Discovery) / 解决策略**:
    - **投票 (Voting)**: 少数服从多数。
    - **基于质量 (Quality-based)**: 信任高权重的来源（例如，信任 Wiki 大于 信任 微博评论）。
    - **关系依赖 (Relation Dependency)**: 利用数据间的相关性来推断真值。
