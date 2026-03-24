# COMP 5575 Lecture 1 笔记

## Introduction to High-Dimensional Data

---

## 1. 课程基本信息（Course Information）

### 1.1 课程名称

**COMP 5575: Advanced Techniques for High-Dimensional Data Management and Analytics**
本讲是 **Lecture 1 - Introduction to High-Dimensional Data**。

### 1.2 任课老师

- **Dr. Haoyang LI**
- Department of Computing, PolyU
- 研究方向（Research Interests）：
    - Data Management
    - Agent and LLMs
    - Security and Privacy
- Email: `haoyang-comp.li@polyu.edu.hk`
- Office: **PQ 810**
- Office hour: **Wednesday 15:00–17:00**

### 1.3 老师提到的实际 AI 应用

老师展示了他参与或关注的一些已上线 AI 应用场景，例如：

- Emoji search
- Service searching
- Spam official account detecting
- Video/article recommendation
- AI for chip design

这说明这门课不是只讲理论，而是强调 **高维数据（high-dimensional data）技术如何落地到真实系统**。

---

## 2. 课程目标与学习成果（Learning Outcomes）

到课程结束时，学生应能够：

1. **解释并比较** 高维数据管理和分析中的先进技术与模型，覆盖：
    
    - time series
    - graph
    - image data
        
2. **应用并评估** 一些前沿方法去解决真实问题，例如：
    
    - RAG（Retrieval-Augmented Generation，检索增强生成）
    - vector search（向量检索）
    - AI agents（智能体）
        
3. **批判性分析** 当前研究与工业实践，并能通过书面和口头形式清晰表达结果。

---

## 3. 课程安排与考核方式（Schedule & Assessment）

### 3.1 上课时间与地点

- 每周一 **18:30–21:20**
- 时间大致分为：
    - 18:30–19:20
    - 19:20–19:30 break
    - 19:30–20:20
    - 20:20–20:30 break
    - 20:30–21:20（lecture / tutorial / invited talks）
- 地点：**QR504**
    老师说明课程内部 lecture 和 tutorial 时间可能会灵活调整。

### 3.2 教材

- **没有官方教材（NO official textbook）**
- 课件对完成 assessment 已经足够
- 推荐扩展书目包括：
    - _Foundations of Multidimensional and Metric Data Structures_
    - _Similarity Search: The Metric Space Approach_
    - _Mining of Massive Datasets_
    - _An Introduction to Statistical Learning_

### 3.3 成绩构成

- **No Assignment**
- **Mid-term Exam：10%**
    - in-person
    - open-book
    - 日期：**2026-03-02**
- **Research Project：20%**
    - due on **April 18**
- **Final Exam：70%**
    - in-person
    - open-book
    - 时间：**23 Apr – 9 May**
- 学校要求：**Final exam ≥ 70%**

### 3.4 Project 要求

- 建议 **3–4 人一组**
- 找一个“好且有趣”的场景/主题
- 例子：**Good QA system for campus life**
- 要求使用 **high-dimensional analysis technique/model** 去解决问题
- 老师特别强调：
    - **实用性（practicability）更重要**
    - **方法新颖性（novelty）不是第一优先级**
    - 重点是你怎么说明并解决挑战
- 报告要求：
    - **6 pages or above**
    - **references 不计入这 6 页**
    - 用老师提供的 **IEEE template**
    - 提交 **PDF**
    - 不接受手写
    - 会做 plagiarism checking
    - plagiarism 直接 **ZERO score**

### 3.5 课程政策

- 有问题可 office hour、预约、或邮件联系
- late penalty：
    - **24 小时内迟交：75% full score**
    - **超过 24 小时：0 分**
- 可以使用 AI 来 **polish** project report
- 但要注意：AI（如 GPT-4o）可能生成错误内容，不能盲信。

---

## 4. 为什么会有这门课？（Why do we have this course?）

课件想表达的核心思想是：

> **现代 AI 正在变成能够感知（perceive）、推理（reason）、行动（act）的复杂智能体。为了携带和处理复杂信息，我们需要高维数据。**

### 4.1 什么是高维数据（high-dimensional data）？

“维度（dimension）”可以简单理解成：**描述一个对象所用的特征数（number of features）**。

比如：

- 一张 **100 × 100** 的灰度图像
    → 可以看成 **10,000 维**
    
- 文本可以变成高维词向量或 embedding
- 时间序列（time-series）是一串按时间排列的数值
- 社交图（social graph）包含节点与关系
- 多模态数据（mixed / multi-modal data）还会把文字、图像、音频等合在一起

### 4.2 课程中的四个例子

#### 例 1：RAG 中的序列数据（Sequential Data in RAG）

LLM 有上下文窗口限制，不能一次“真的读完”海量文档。
所以我们会先把文档变成向量（vector），再做向量检索（vector retrieval），从海量资料中找出最相关内容喂给 LLM。这样就像让模型“快速查阅一整座图书馆”。

#### 例 2：多模态感知中的图像数据（Image Data in Multimodal Perception）

图像/视频本质上是像素（pixels），但机器更适合处理的是高维向量表示。
课件提到 **CLIP**：它把图像和文本映射到同一个语义空间中，让模型能理解“这张图”和“这句话”是不是对应。老师还提到 CLIP 为 Stable Diffusion 一类 text-to-image 系统成功奠定了基础。

#### 例 3：知识推理中的图数据（Graph Data in Reasoning）

复杂问题常常不是单点知识，而是**关系网络（relationships）**。
知识图谱（knowledge graph）或图嵌入（graph embeddings）把实体与关系表示成高维结构，使模型能做 **multi-hop reasoning（多跳推理）**。

#### 例 4：科学发现中的高维空间（Scientific Discovery）

像蛋白质折叠（protein folding）、药物发现（drug discovery）等问题，本质上都在超高维空间里搜索和建模。
AI / agents 可以在这些高维空间中做模拟，帮助解决人类难以直接处理的问题。

---

## 5. 高维数据的伦理问题（Ethic Issue in High-dimensional Data）

课件提到两个非常重要的问题：

1. **Wrong response from AI**
2. **How to guarantee the moral of AI**

这说明高维数据不只是“技术越强越好”，还涉及：

- 错误回答造成的现实伤害
- 数据偏差（bias）
- 安全与隐私（security and privacy）
- AI 是否会被滥用
- 如何让系统符合伦理与社会规范

老师还举了反洗钱（anti-money laundering）和 AI 聊天机器人带来伤害的例子，说明高维数据分析系统一旦进入现实世界，责任问题就非常重要。

---

## 6. 课程整体设计（Course Design）

课件给出一个很浓缩的公式：

# AI in HD = Data + Models + Computing Power

也就是说，这门课不是只讲模型，而是把三件事连起来看：

1. **Data**：高维数据是什么、怎么表示
2. **Models**：用什么模型处理
3. **Computing Power**：算力如何支撑这些方法

课程主题覆盖：

- Introduction to High-dimensional Data
- Multi-dimensional Decision
- Knowledge Graphs
- Time-series / Sequential Data
- Large Language Models
- RAG
- Vector Search
- GNN
- Computer Vision
- Agents
- Attack and Defense
- AI ethics

---

## 7. 详细课程进度（Detailed Schedule）

大致进度如下：

1. **Lecture 1**: Introduction to High-Dimensional Data
2. **Lecture 2**: Decision Strategies on Multi-dimension Data
3. **Lecture 3**: Knowledge Graph and Applications
4. **Lecture 4**: Time-series Data Analysis and Applications
5. **Lecture 5**: Large Language Models with Applications
6. **Lecture 6**: Retrieval-augmented Generation with Applications
7. **Mid-term + Lecture 7**: Vector Search
8. **Lecture 8**: Graph Neural Network with Applications
9. **Lecture 9**: Computer Vision Models with Applications
10. **Lecture 10**: Agents
11. **Lecture 11**: Attack and Defense of High-dimensional Data
12. **Project presentation + Course review**

---

## 8. 高维数据挖掘的发展历史（Developing History of High-dimensional Data Mining）

课件强调：
**高维数据不是突然出现的新概念，而是从统计学（statistics）、信息检索（information retrieval）、数据库（databases）、机器学习（machine learning）一路演化而来。** 每一波技术发展都会带来新问题和新方法。

### 8.1 早期：特征工程（feature engineering）

早期的高维数据，很多来自 **人工构造特征**：

- 把 text、images、logs、sensor features 拼接到一起
- 得到一个很长的向量（long vector）

这就是典型的：

> **先设计特征，再喂给模型**

优点是可解释；缺点是很依赖人工经验，而且难以覆盖复杂语义。

### 8.2 维度约简（dimensionality reduction）与 PCA

当很多变量彼此相关（correlated）时，可以降低维度，同时保留主要模式（main pattern）。
这里最经典的方法就是 **PCA（Principal Component Analysis，主成分分析）**。

课件提到：

- Pearson (1901) 提出
- Hotelling (1933) 发展完善

**直观理解：**
原来数据有很多维，但其中不少维度表达的是重复信息。
PCA 的目标就是找到“最能解释数据变化方向”的几个新坐标轴，把原数据压缩到更低维。

### 8.3 维度灾难（Curse of Dimensionality）

这是高维数据最核心的概念之一。

随着维度增加：

- 空间体积急剧膨胀
- 数据在空间中变得越来越稀疏（sparse）
- 传统距离度量变得不再可靠
- 统计显著性也会变弱

课件把这个现象称为 **Curse of Dimensionality**，并提到 Richard Bellman (1957)。

**通俗理解：**
在 2 维平面里，“近”与“远”还比较直观；
但到了几百维、几千维后，很多点之间的距离会变得“差不多”，这会让最近邻搜索、聚类、分类都变难。

---

## 9. 从信息检索到向量检索（From IR to Vector Search）

课件指出，信息检索里，物品常被表示成 **高维稀疏向量（high-dimensional sparse vectors）**。
之后我们做两件事：

1. **Build**：构造向量表示
2. **Query Indexing**：构建索引，让查询更快

老师把它概括为：

> **High-dimensional data management and analytics = Better Build + Query Indexing**

这句话很重要，因为它说明高维数据系统不仅仅是“模型好不好”，还要看：

- 向量表示是否好
- 索引结构是否好
- 查询速度是否可接受

---

## 10. k-NN、ANN 与高维检索（Query Indexing）

### 10.1 k-NN（k-Nearest Neighbors）

最直接的任务是：

> 给定一个 query，找到距离它最近的 k 个向量

如果要求完全精确，那就是 **Exact k-NN**。

### 10.2 ANN（Approximate Nearest Neighbors）

在大规模系统中，完全精确通常太慢，因此会接受近似解：

> **牺牲一点点准确率，换取巨大的速度提升**

课件给的例子是：

- recall 可能是 **0.95**
- 速度可能提升到 **500×**

这就是为什么现实中的向量数据库、RAG 系统、大规模推荐系统都特别重视 **ANN**。

### 10.3 暴力搜索（Brute-force / Linear Scan）

最朴素的方法：

- 把 query 和数据库里每一个向量都算一遍距离

时间复杂度：

- **O(N · D)**

其中：

- `N` = 向量个数
- `D` = 维度数

当 N 很大、D 很高时，这种方法几乎不可用。

### 10.4 更好的索引思想：Prune

更好的查询索引的核心思想是：

> **先尽量剪枝（prune）掉不可能的点，再做精细计算**

也就是：

- 尽量不看大多数点
- 或先只看部分维度 `d`，其中 `d << D`
- 为此要设计好的数据结构（data structure）去排除“不可能成为近邻”的候选点

### 10.5 LSH（Locality Sensitive Hashing）

LSH 的思想是：

- **相似向量以高概率落到同一个 bucket**
- 查询时只搜少数 bucket
- 跳过大量无关数据

优点：

- 快
    缺点：
    
- 结果通常是近似的
    本质上仍然是在做 **速度—准确率（speed–accuracy trade-off）**。

---

## 11. 深度学习如何改变高维数据处理（Deep Learning Era）

### 11.1 早期瓶颈：算力不够

课件提到，在 2000 年代早期：

- 硬件条件限制了神经网络的发展
- 三层左右的神经网络通常不如很多统计机器学习方法
- 当时很多“大胆想法”依然是基于 CPU 计算

也就是说，当时不是“没人想到深度学习”，而是 **想到了，但算不动**。

### 11.2 GPU 时代

一个关键节点是：

- **2006 年 NVIDIA 发布 CUDA**

这使得神经网络训练进入 GPU 加速时代，深度学习才真正爆发。

### 11.3 从特征工程走向表示学习（representation learning）

深度学习的重要变化：

1. 减少人工特征工程
2. 自动学出 **dense high-dimensional vectors（稠密高维向量）**
3. 模型性能随数据规模扩大而提升

这代表范式变化：

- 过去：人设计特征
- 现在：模型自己学表示（representation）

### 11.4 视觉突破

课件提到：

- **CNNs** 在 2012 年 AlexNet 后统治视觉任务
- **ResNet** 通过缓解梯度消失（gradient vanishing）支持更深网络
- 高维像素数据被映射成更语义化的特征

核心思想：

> 原始像素并不等于“语义”，深层网络的任务就是把低层像素一步步变成高层语义表示。

### 11.5 优化引擎

深度学习的进步不只靠网络结构，也靠优化：

- SGD
- Adam
- Dropout 等 regularization
- ImageNet 等 benchmark 推动快速迭代

---

## 12. 大模型时代（Era of Large Language Models）

课件给出一个大致演进路线：

1. **1950s–1990s：Symbolic Systems**
    
    - rule-based
    - logical reasoning
    - symbolic operations
        
2. **1990s–2000s：Statistical Learning**
    
    - 更依赖数据统计规律
        
3. **2000s–2018：Deep Learning**
    
    - neural networks
    - pattern recognition
    - automatic feature learning
        
4. **2019–Present：Large Language Models**
    
    - pre-training
    - big data
    - adaptive
    - data-driven
    - self-learning

### 12.1 大模型应用方向

课件还概述了多类大模型应用：

- **Text large models**
- **Visual large models**
    - AI painting
- **Audio large models**
    - virtual character / chatbot / anchor / singer
- **Sequence large models**
    - healthcare / weather / finance / manufacturing / power systems
- **Multimodal large models**
    - images + text + audio + video 统一表示

这说明“高维数据”几乎就是现代大模型的基础输入形式。

### 12.2 本章总结出的高维分析挑战

课件明确列了五个挑战：

- High dimensional
- Sparse pattern
- Complex correlation
- Large data volume
- Time-aware data evolving

这五点后面会贯穿整门课。

---

## 13. 数据属性类型（Data Attribute Types）

这一部分是基础中的基础，后面做相似度、聚类、分类时都离不开。

### 13.1 总分类

课件把属性类型分成：

- **Qualitative（定性）/ Non-Numeric**
- **Quantitative（定量）/ Numeric**

进一步分为：

- Nominal
- Binary
- Ordinal
- Numeric
    - Interval-scaled
    - Ratio-scaled
- Discrete
- Continuous

---

## 14. Nominal（名义型）

### 定义

Nominal data 是通过**名称或标签**来区分类别的数据，没有高低顺序。
例如：

- gender
- hair color
- animal type

特点：

- 只是“类别不同”
- 没有“谁更大、谁更好”这种关系
- 类别彼此独立、互斥（mutually exclusive）

### 直观理解

“红色、蓝色、绿色”只是在分组，不存在“蓝色比红色大”。

---

## 15. Ordinal（有序型）

### 定义

Ordinal data 也是分类数据，但它**有顺序（order / rank）**。
例如：

- Bachelor’s < Master’s < PhD
- Grade C < B < A

但注意：

> 它只告诉你顺序，不告诉你相邻两级之间差多少。

### 直观理解

你知道“硕士高于本科”，但“本科到硕士”和“硕士到博士”的差距不能简单视为相同。

---

## 16. Binary（二元型）

### 定义

Binary 是只有两个状态的 nominal attribute。
常见表示：

- 1 / 0
- true / false
- present / absent
- positive / negative

### 两类 Binary

#### 1）Symmetric binary

两个结果同等重要。
例如某些纯分类标签。

#### 2）Asymmetric binary

两个结果不等重要。
例如医学检测：

- disease positive
- disease negative

通常把更重要、更值得关注的结果编码为 **1**。

---

## 17. Numeric（数值型）

课件把 numeric 分成两种：

### 17.1 Interval-scaled（区间尺度）

特点：

- 数值之间间隔均匀
- **没有真正的 zero point（真实零点）**

课件举例：

- temperature（摄氏温度）
- time of day

例如：

- 10°C 和 20°C 的差值有意义
- 但不能说 20°C 是 10°C 的两倍热
- 0°C 也不代表“温度的起点”

### 17.2 Ratio-scaled（比率尺度）

特点：

- 间隔均匀
- **有真实零点**

例如：

- age
- weight
- height
- spend time

因为有真实零点，所以像“20 kg 是 10 kg 的两倍”这种说法才有意义。

---

## 18. Discrete vs Continuous（离散 vs 连续）

### 18.1 Discrete（离散）

- 取值有限，或可数无限
- 常见：
    - hair color
    - marital status
    - medical test
    - counts
- 计算机里常表示为整数变量

### 18.2 Continuous（连续）

- 取值是实数
- 常见：
    - temperature
    - height
    - weight
    - length
    - time
- 计算机里一般用浮点数表示

---

## 19. 数据类型（Data Types）

课件列出了常见数据类型，并说明它们在 humanities 或真实应用中的含义。

### 19.1 Table（表格）

- 行 + 列的结构化数据
- 例子：
    - census data
    - archaeological site catalogs
    - linguistic frequency tables
- 应用：
    - demographic patterns
    - historical artifact cataloging

### 19.2 Textual Data（文本）

- written / printed words
- 例子：
    - historical manuscripts
    - novels
    - letters
    - academic texts
- 应用：
    - textual analysis
    - sentiment analysis
    - language evolution

### 19.3 Time Series（时间序列）

- 数据点按时间顺序排列
- 例子：
    - climate records
    - population growth
    - migration timelines
- 应用：
    - climate change tracking
    - stock trend analysis

### 19.4 Graph Data（图数据）

图数据在现实中非常常见：

- social network
- molecule graph
- knowledge graph

课件给出图表示：

- `G(V, A, X)`
    - `V`：节点集
    - `A`：邻接矩阵（adjacency matrix）
    - `X`：节点特征矩阵（node feature matrix）

### 19.5 Image（图像）

- 像素数组或向量形式存储
- 例子：
    - paintings
    - photographs
    - maps
- 应用：
    - visual culture
    - historical maps
    - digitization / preservation of artworks

### 19.6 Video（视频）

- 随时间变化的视觉 + 音频序列
- 例子：
    - documentaries
    - historical footage
    - interviews

### 19.7 Audio（音频）

- waveform 或数字音频文件
- 例子：
    - oral histories
    - music recordings
    - speeches
- 应用：
    - linguistic pattern analysis
    - endangered language preservation
    - sound evolution study

### 19.8 Multi-modal（多模态）

Multi-modal data 指：

> 同时包含多种模态的信息，如 text + image + audio + video。

---

## 20. 为什么要计算相似度（Why compute similarity?）

课件说，相似度（similarity）在很多任务里都非常关键，尤其是 clustering。
因为聚类本质上就是在问：

> 哪些样本彼此更像，应该分到一组？

它还可以用于：

- NLP / text analysis
- recommendation systems
- anomaly detection
- content-based filtering

---

## 21. 相似度的应用场景（Applications of Similarity）

### 21.1 文本分析

通过 cosine similarity 等度量文本之间的接近程度，可用于：

- document clustering
- plagiarism detection
- recommendation systems

本质上就是把文本先 embedding 成向量，再比较向量相似度。

### 21.2 个性化推荐

系统根据用户行为与物品特征，找出“与用户喜欢内容相似”的物品并推荐。
例如课件中的电影推荐例子。

### 21.3 异常点检测（Outlier Detection）

如果某些点和“大多数点”距离很远，它们可能是 outliers。
在金融风控中可以用于发现欺诈交易。

### 21.4 内容过滤（Content-based Filtering）

根据用户之前喜欢过的内容，推荐特征相近的新内容。
例如音乐 app 推荐风格相似歌曲。

### 21.5 知识发现（Knowledge Discovery）

课件强调：

- similarity / dissimilarity 依赖具体场景
- 相似问题可能有相似解法
- 它支持 clustering、outlier analysis、classification 等任务

---

## 22. Jaccard Similarity（杰卡德相似度）

### 22.1 定义

Jaccard Similarity 常用于：

- asymmetric binary vectors
- 两个集合（sets）的相似度

公式：

[
J(A,B)=\frac{|A\cap B|}{|A\cup B|}
]

意思是：

> 交集占并集的比例有多大。

### 22.2 直观理解

如果两个集合完全一样：

- 交集 = 并集
- Jaccard = 1

如果两个集合完全没有重合：

- 交集为空
- Jaccard = 0

### 22.3 应用

- document similarity
- recommendation systems
- image similarity

---

## 23. Cosine Similarity（余弦相似度）

### 23.1 定义

Cosine similarity 衡量的是两个向量**方向（direction）**是否相近，而不太关注它们的长度（magnitude）。

公式：

[
\cos \theta = \frac{\mathbf{x}\cdot \mathbf{y}}{|\mathbf{x}||\mathbf{y}|}
]

其中：

- (\mathbf{x}\cdot \mathbf{y}) 是点积（dot product）
- (|\mathbf{x}|) 是向量长度（norm）

### 23.2 为什么它很适合文本？

因为文本向量里：

- 文档长短不同
- 词频总量不同

如果直接看大小，长文档可能天然“更大”；
但余弦相似度会做归一化，更关注“分布方向是否相似”。

### 23.3 应用

- information retrieval
- text clustering
- TF / document vector comparison
- biological taxonomy
- gene feature mapping

---

## 24. 相似度与距离的关系（Similarity vs Distance）

### 24.1 相似度

- 越大表示越像

### 24.2 距离（distance / dissimilarity）

- 越小表示越像
- 越大表示越不像

课件给了一个简单关系例子：

[
Dis(a,b)=1-sim(a,b)
]

虽然这不是所有情况都适用，但它很好地表达了二者的互补关系。

---

## 25. Minkowski Distance（闵可夫斯基距离）

这是一个非常重要的统一框架。
对两个 (l) 维向量 (i, j)，Minkowski distance 是 (L_p) 范数的一种形式。课件还强调，一个合法的 metric 需要满足：

- positivity
- symmetry
- triangle inequality

---

## 26. Manhattan Distance（曼哈顿距离，L1）

### 定义

当 (p=1) 时，Minkowski distance 就变成 Manhattan distance。

本质上是：

> 每个维度差值绝对值之和

[
d(i,j)=\sum |x_{if}-x_{jf}|
]

### 直观理解

像在棋盘或城市网格里走路：

- 只能横着走、竖着走
- 不能直接斜穿过去

### 应用

- pathfinding
- robotics
- warehouse / city grid navigation

---

## 27. Euclidean Distance（欧几里得距离，L2）

### 定义

当 (p=2) 时，就是最熟悉的直线距离：

[
d(i,j)=\sqrt{\sum (x_{if}-x_{jf})^2}
]

### 直观理解

就是两点之间“直线最短距离”。

### 应用

- image processing
- recommendation systems
- clustering

---

## 28. Chebyshev / Supremum Distance（切比雪夫距离，L∞）

### 定义

当 (p \to \infty) 时：

[
d(i,j)=\max_f |x_{if}-x_{jf}|
]

意思是：

> 只看所有维度里“差得最大”的那一维。

### 应用

- game theory（worst-case）
- quality control（最大偏差）

---

## 29. Hamming Distance（汉明距离）

### 定义

用于比较两个**等长二进制字符串**，看它们有多少个位置不同。

例如：

- `11011001`
- `10011101`

做 XOR：

- `01000100`

结果里有两个 1，因此 Hamming distance = **2**。

### 应用

- binary strings
- error-correcting codes
- bit-level comparison

---

## 30. 有序属性的接近度（Proximity for Ordinal Attributes）

Ordinal 不能直接像 nominal 那样只判“同/不同”，因为它有顺序。
课件的做法是：

### 30.1 第一步：转成 rank

如果一个 ordinal attribute 有 (M_f) 个状态：

- 用 rank (r_f \in {1,\dots,M_f}) 表示

### 30.2 第二步：映射到 ([0,1])

[
z_f=\frac{r_f-1}{M_f-1}
]

例如：

- freshman → 0
- sophomore → 1/3
- junior → 2/3
- senior → 1

### 30.3 第三步：按 numeric 方式算距离

例如用 L1 distance：

- freshman 和 senior 的距离 = 1
- junior 和 senior 的距离 = 1/3

---

## 31. 混合类型属性的距离（Mixed Types Dissimilarity）

现实数据经常同时包含：

- nominal
- binary
- ordinal
- numeric

所以要把不同属性的“差异”组合起来。
课件给出加权公式：

[
d(i,j)=\frac{\sum w_{ij}^{(f)} d_{ij}^{(f)}}{\sum w_{ij}^{(f)}}
]

其中：

- (w_{ij}^{(f)})：第 (f) 个属性的权重
- (d_{ij}^{(f)})：对象 (i,j) 在第 (f) 个属性上的差异

### 31.1 各类属性如何算差异

- **numeric**：先归一化，再算距离
- **binary / nominal**：
    - 一样 → 0
    - 不一样 → 1
- **ordinal**：
    - 先 rank
    - 再 map 到 [0,1]
    - 再按 numeric 处理

### 31.2 课件中的例子

四个对象 A, B, C, D 有三类特征：

- Test-1：Nominal
- Test-2：Ordinal
- Test-3：Numerical

权重：

- Nominal：0.2
- Ordinal：0.5
- Numerical：0.3

课件算出了：

- (d(A,B)=0.865)
- (d(A,C)=0.585)
- (d(A,D)=0.120)

说明在综合考虑三类属性后，**A 与 D 最相近**。

### 31.3 这部分的意义

这是非常实用的，因为现实世界的数据几乎总是 mixed-type。
比如一个学生数据表可能同时有：

- 专业（nominal）
- 年级（ordinal）
- 成绩（numeric）
- 是否奖学金（binary）

如果你不会混合属性距离，很多聚类/推荐/相似搜索任务就做不好。

---

## 32. 混合属性的应用（Applications for Mixed Types）

课件提到三个方向：

1. **Data Preprocessing**
2. **Machine Learning Algorithms**
3. **Survey Analysis**

尤其是：

- decision trees
- ensemble methods

这类模型往往比较适合处理 mixed attributes。

---

## 33. 本讲最核心的知识主线（你复习时最该抓住的内容）

### 主线 1：什么是高维数据

高维数据不是某一种特殊格式，而是：

> **当描述对象需要很多维特征时，就进入高维问题。**

它可以是：

- text
- image
- graph
- time series
- audio
- video
- multimodal

### 主线 2：为什么高维数据难

最主要原因：

- 维度高
- 数据稀疏
- 相关性复杂
- 数据量大
- 还会随时间演化

### 主线 3：现代 AI 为什么离不开高维表示

无论是：

- RAG
- CLIP
- GNN
- protein folding
- multimodal models

本质上都在做：

> **把复杂对象表示为高维向量 / 张量，再在这些表示空间中做检索、匹配、推理、生成。**

### 主线 4：为什么要学相似度和距离

因为高维分析里，很多任务最后都会变成：

- 哪些东西最像？
- 哪些东西最不像？
- 哪些点该归成一类？
- 哪些点是异常点？
- 哪些内容该被推荐？

### 主线 5：数据类型决定处理方法

不同属性类型不能乱用同一种距离：

- nominal 不能直接算大小
- ordinal 不能假设间隔已知
- interval 不能随便谈倍数
- ratio 才有真正零点

这是后面做建模时非常容易错的地方。

---

## 34. 本讲总结（Summary）

这节课主要做了四件事：

### 1）交代整门课的框架

这门课围绕高维数据展开，涵盖：

- vector search
- RAG
- knowledge graph
- GNN
- CV
- agents
- 安全与伦理

### 2）说明高维数据为何重要

现代 AI 要处理复杂信息，就必须依赖高维表示。

### 3）回顾高维数据方法的发展脉络

从：

- feature engineering
- PCA
- curse of dimensionality
- IR / indexing
- ANN / LSH
- deep learning
- large models

一路发展到今天。

### 4）打基础：认识数据和距离

本讲后半部分其实是在给后面的所有算法铺路，核心基础包括：

- attribute type
- data type
- similarity
- distance
- mixed-type dissimilarity

课件最后一句总结得很精炼：

> Data objects consist of datasets, represent entities, and are described by attributes. Attributes can be nominal, binary, ordinal, or numeric. Proximity includes similarity and dissimilarity (distance).
