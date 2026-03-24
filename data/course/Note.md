### <span style="background:#fff88f">为什么文本数据使用余弦相似度</span>

文本通常表示成 TF-IDF 或 embedding。文档的长度（字数/词频总量）会让向量的幅度变化很大，但这不一定代表语义变化。余弦相似度把向量归一化，只比较方向，因此更关注词分布/语义方向，能减弱长短差异和整体频次差异的影响。在高维稀疏的文本空间里，这种角度相似度也更稳定、更符合信息检索的需求。Text is usually represented as **TF-IDF** or **embeddings**. The length of a document (word count / total term frequency) can cause large changes in the magnitude of its vector, but this does not necessarily indicate a change in semantics. **Cosine similarity** normalizes the vectors and compares only their directions, so it focuses more on **word distribution** or **semantic direction**, reducing the influence of differences in document length and overall term frequency. In the **high-dimensional sparse space** of text, this kind of angular similarity is also more stable and better suited to the needs of **information retrieval**.

### <span style="background:#fff88f">计算混合数据的相似度</span>

- **单独算：** 针对每一列，用它该用的方法（Numeric, Nominal, Ordinal 等）计算差异。
- **缩放到 [0, 1]：** 强行把所有差异都拉到 0 到 1 之间（否则“工资”的差异会淹没“年龄”的差异）。
- **求平均：** 把所有列的差异加起来除以列数。

### K-Means++ 的核心算法

K-Means++ 将“纯随机”改成了“加权随机”。具体步骤如下：

1. **第一步：** 从数据集中 **随机** 选择 1 个点作为第一个质心 $c_1$。
2. **第二步：** 对于数据集中的每一个点 $x$，计算它到**当前已选出的最近质心**的距离，记为 $D(x)$。 $$D(x) = \min_{c \in \text{selected}} \|x - c\|$$
3. **第三步：** 选择下一个质心 $c_{next}$。
    - **关键点：** 我们不是随机选，而是根据概率选。点 $x$ 被选为下一个质心的概率 $P(x)$ 与其距离的平方 $D(x)^2$ 成正比。
    - $$P(x) = \frac{D(x)^2}{\sum_{x'} D(x')^2}$$
    - _直觉：_ 离现有质心越远的点，$D(x)$ 越大，被选中的概率就越高。
4. **第四步：** 重复步骤 2 和 3，直到选出 $K$ 个质心。
5. **第五步：** 使用这 $K$ 个点作为初始值，开始运行标准的 K-Means 算法（Lloyd's Algorithm）。

## Lecture 3

### 🔗 数据集成 (Data Integration)

**1. 核心定义 (Definition)**
数据集成是将来自**多个数据源 (Multiple Sources)** 的数据合并到一个**一致的数据存储 (Coherent Data Store)**（如数据仓库）中的过程。
- **目标**: 解决数据分散问题，为后续的高维分析提供统一视图。

**2. 主要挑战 (Key Issues)**
在合并数据时，我们会遇到以下几个核心问题：
- **实体识别问题 (Entity Identification Problem)**:
    - **问题**: 如何确定不同数据库中的属性是指同一个东西？
    - **例子**: 数据库 A 中的 `customer_id` 和数据库 B 中的 `cust_number` 是否指代同一个实体？
    - **解决**: 需要进行模式集成 (Schema Integration) 和元数据 (Metadata) 匹配。
- **冗余问题 (Redundancy)**
    - **来源**:
        1. **派生属性**: 一个属性可能是由另一个属性推导出来的（例如：`age` 可以由 `birthday` 计算得出）。
        2. **重复信息**: 同样的属性在不同表中重复存储。
    - **解决**: 使用**相关性分析 (Correlation Analysis)** 检测冗余（见下文详解）。
- **数据值冲突 (Data Value Conflict)**:
    - **问题**: 针对同一实体的同一属性，不同来源的值不同。
    - **原因**: 表示方式不同（如公制 vs 英制）、比例尺度不同（如 5分制 vs 100分制）。

### 📉 冗余处理：相关性分析 (Handling Redundancy: Correlation Analysis)

这是考试中计算题的**重灾区**。PPT 重点介绍了针对**数值型数据 (Numeric Data)** 的两种度量方法。

#### 1. 协方差 (Covariance)

用于衡量两个变量如何一起变化。

- **公式 (Sample Covariance)**:
    $$Cov(A, B) = \frac{\sum_{i=1}^{n} (a_i - \bar{a})(b_i - \bar{b})}{n-1}$$
    - $\bar{a}, \bar{b}$: 属性 A 和 B 的样本均值。
    - $n$: 样本数量。
- **判定**:
    - $Cov > 0$: 正相关 (A 增 B 增)。
    - $Cov < 0$: 负相关 (A 增 B 减)。
    - $Cov = 0$: 独立/无关。

#### 2. 相关系数 (Correlation Coefficient)

用于衡量线性关系的**强度 (Strength)** 和 **方向 (Direction)**。它是标准化后的协方差。

- **公式**:
    $$Corr(A, B) = \frac{Cov(A, B)}{\sigma_A \sigma_B} = \frac{\sum (a_i - \bar{a})(b_i - \bar{b})}{(n-1) \sigma_A \sigma_B}$$
    - $\sigma_A, \sigma_B$: 标准差 (Standard Deviation)。
- **优势**: 它是去量纲的 (Unitless)，取值在 $[-1, 1]$ 之间，比协方差更容易解释。
- **应用**: 如果两个属性的相关系数非常高（如 $>0.9$），则其中一个可能被视为冗余并被移除，以减少高维数据的复杂性。

### 🧩 实体解析 (Entity Resolution / Entity Matching)

这是解决 **元组重复 (Tuple Duplication)** 的关键技术。

**1. 场景 (Scenario)**

识别来自不同来源的、指向现实世界中同一实体的记录。

- **Entry 1**: `Annabella Smith`, `St Andrews New York`, `Annabellasmith@email.com`
- **Entry 2**: `Anna Smith`, `Saint Andrews NY`, `Annasmith@email.com`
**2. 处理流程 (Process Pipeline)**
PPT 提供了一个标准的三步走流程，建议写在笔记中作为“算法步骤”：
1. **数据标准化 (Data Standardization)**:
    - 统一格式，消除格式差异。
    - _操作_: 转小写 (Lowercase)、分割字符串 (Split)、去除标点 (Remove punctuation)。
    - _结果_: `Anna-bella-Smith` vs `Anna-Smith`。
2. **相似度匹配 (Similarity Matching)**:
    - 使用字符串距离算法（如 **Levenshtein distance** / 编辑距离）计算属性间的相似度。
    - _结果_: 计算得出相似度分数 $S(E1, E2) = 0.65$。
3. **合并/决策 (Decision/Merge)**:
    - 设定阈值 (Threshold)，例如 $0.80$。
    - _判定_: 如果 $S < Threshold$，则视为不同实体；如果 $S \ge Threshold$，则合并。
    - _PPT 案例结论_: $0.65 < 0.80$，因此判定为不匹配（或者需要人工介入）。

### 数据归约 (Data Reduction)

**核心目标 (Goal)**：
获得数据集的缩小表示 (Reduced representation)，但在其上挖掘出来的分析结果与原始数据几乎一致 (Almost the same analytical results)。
**为什么需要？**：
数据仓库可能有 TB 级的数据，在完整数据集上运行复杂的数据挖掘算法可能需要几天甚至几周。

#### 1. 维度归约 (Dimensionality Reduction)

**核心思想**：减少所考虑的随机变量或属性的数量 ($d$)。
PPT 将其细分为**特征提取**和**特征选择**两类。

##### A. 特征提取 (Feature Extraction)

- **定义**：将高维数据**变换 (Transform)** 到一个更低维的空间。
- **核心技术**：**主成分分析 (Principal Component Analysis, PCA)**。
  - PCA 寻找正交变换，将原始的（可能相关的）变量转换为一组线性不相关的变量（主成分）。
  - 它不仅是降维，还是一种发现数据内部结构的方法。

##### B. 属性子集选择 (Attribute Subset Selection) / 特征选择

- **定义**：识别并保留原始属性的一个**子集 (Subset)**，剔除不相关 (Irrelevant) 或冗余 (Redundant) 的属性。
- **挑战**：如果有 $d$ 个属性，就有 $2^d$ 个可能的子集。穷举搜索是不可能的，因此必须使用**启发式方法 (Heuristic Methods)**（贪心策略）。
**四种关键启发式算法 (Heuristic Methods)**:
1. **逐步向前选择 (Stepwise Forward Selection)**:
   - 初始状态：空集。
   - 操作：每一轮扫描剩余属性，选择**最好**的一个加入集合。
   - *什么叫最好？* 通常指统计显著性最高（如 P-value 最小）或信息增益最大。
2. **逐步向后淘汰 (Stepwise Backward Elimination)**:
   - 初始状态：全集 (所有属性)。
   - 操作：每一轮扫描当前属性，移除**最差**的一个。
3. **组合策略 (Combination of Forward & Backward)**:
   - 操作：每一步既可以选最好的加入，也可以把变差的移出。
   - *优势*：比单向搜索更灵活，能找到更优解。
4. **决策树归纳 (Decision Tree Induction)**:
   - **原理**：决策树构建过程本身就是在做属性选择（通常基于信息增益）。
   - **结论**：
     - 出现在树节点上的属性 $\rightarrow$ **保留 (Good)**。
     - 从未出现在树上的属性 $\rightarrow$ **剔除 (Irrelevant)**。

#### 2. 数量归约 (Numerosity Reduction)

**核心思想**：通过选择替代的、较小的数据表示形式来减少数据量（减少行数 $N$）。
PPT 将其分为**参数化**和**非参数化**两类。

##### A. 参数化方法 (Parametric Methods)
建立一个模型来估计数据，只需存储模型参数，丢弃实际数据。
- **回归 (Regression)**:
  - **线性回归 (Linear Regression)**: 数据被建模为直线 $Y = wX + b$。只需存储 $w$ 和 $b$。
  - **多元回归 (Multiple Regression)**: 数据被建模为多维曲面，允许涉及多个预测变量。
- **对数线性模型 (Log-Linear Models)**:
  - 近似给定元组在多维空间中每个点的离散概率分布。

##### B. 非参数化方法 (Non-Parametric Methods)
不假设模型，直接处理数据分布。
- **1. 直方图 (Histograms)**
  - 将数据划分为桶 (Buckets/Bins)，存储每个桶的统计量（如 sum, count）。
  - **分桶规则**:
    - **等宽 (Equal-width)**: 每个桶的数值范围区间相等（如 $0-10, 10-20$）。*缺点*：受离群点影响大。
    - **等频 (Equal-frequency)**: 每个桶包含相同数量的数据项。*优点*：适应倾斜分布。
- **2. 聚类 (Clustering)**
  - 将数据根据相似性分组。
  - **归约方式**: 用簇的**质心 (Centroid)** 和**直径 (Diameter)** 来代表整个簇的数据。
  - **优势**: 还能顺便检测离群点 (Outliers)。
- **3. 采样 (Sampling)**
  - 用小样本 $s$ 代表大数据集 $N$。
  - **简单随机采样 (Simple Random Sampling, SRS)**:
    - **无放回 (Without Replacement, SRSWOR)**: 抽一个少一个。
    - **有放回 (With Replacement, SRSWR)**: 每次抽完放回，独立重复试验。
    - *缺点*：对**倾斜数据 (Skewed Data)** 效果差。
  - **分层采样 (Stratified Sampling)**: (考试重点)
    - **适用场景**: 数据分布不平衡（如稀有类分析）。
    - **步骤**: 将数据分为互不相交的层 (Strata)，然后在每一层内进行简单随机采样。
    - *优点*: 保证稀有类也能被代表。

#### 3. 数据压缩 (Data Compression)

**核心思想**：使用编码机制减少数据集大小。
- **无损压缩 (Lossless Compression)**:
  - 原始数据可以从压缩数据中**精确重建**。
  - *应用*: 字符串压缩（如 DNA 序列）。
  - *限制*: 通常只能提供有限的压缩率。
- **有损压缩 (Lossy Compression)**:
  - 原始数据只能被**近似重建**。
  - *应用*: 音频、视频、图像。
  - *例子*: 小波变换 (Wavelet Transform)、PCA（也算一种有损压缩）。

| **问题场景 (Scenario)**      | **推荐方法 (Recommended Method)** | **关键词 (Keywords)**                        |
| ---------------------------- | --------------------------------- | -------------------------------------------- |
| **属性太多，无法穷举**       | **Attribute Subset Selection**    | Heuristic, Stepwise, Greedy                  |
| **寻找数据的主要变化方向**   | **PCA**                           | Feature Extraction, Orthogonal, New Features |
| **数据量大，只需线性关系**   | **Regression**                    | Parametric, Model $y=wx+b$                   |
| **数据倾斜，需要分析稀有类** | **Stratified Sampling**           | Skewed Data, Strata                          |
| **需要对多维概率建模**       | **Log-Linear Models**             | Probability Distribution                     |
| **文本数据的压缩**           | **Lossless Compression**          | Exact Reconstruction                         |

没问题，Asimov。以下是根据 Lecture 3 的 PPT 内容重新整理的 **数据变换 (Data Transformation)** 笔记，所有标题层级已降低一级，方便你嵌入到更大的笔记结构中。

---

#### 4.数据变换 (Data Transformation)

**1. 核心定义**

数据变换是将数据映射或转换成适合挖掘的形式的过程 (A function that maps the entire set of values of a given attribute to a new set of replacement values).
- **目的**：让数据更规范，消除量纲影响，提升算法（特别是涉及距离计算的算法，如 KNN, K-Means）的效果。

**2. 变换策略概览 (Strategies)**

PPT 列出了几种主要形式：
- **平滑 (Smoothing)**: 去除数据中的噪声（如分箱、回归、聚类）。
- **属性构造 (Attribute Construction)**: 从给定的属性集构造新的属性（例如：用 `长` $\times$ `宽` 构造 `面积`）。
- **聚集 (Aggregation)**: 对数据进行汇总或聚集（例如：日销售额 $\to$ 月销售额）。
- **规范化/归一化 (Normalization)**: 将数据按比例缩放，使其落入特定的小区间（如 $[0, 1]$）。
- **离散化 (Discretization)**: 将连续属性的原始值用区间标签或概念标签替换。
#### 📏 核心考点：归一化 (Normalization)

这是计算题的重中之重。PPT 详细介绍了三种方法。
##### A. 最小-最大规范化 (Min-Max Normalization)
**原理**：对原始数据进行线性变换，将其映射到用户指定的区间 $[new\_min_A, new\_max_A]$。
- **公式**:

    $$v' = \frac{v - min_A}{max_A - min_A}(new\_max_A - new\_min_A) + new\_min_A$$
    - $v$: 原始值
    - $min_A, max_A$: 属性 A 的原始最小值和最大值
    - $new\_min_A, new\_max_A$: 目标区间的最小值和最大值（通常是 0 和 1）
    - $v'$: 变换后的值
- **PPT 案例**:
    - **已知**: Income 范围 $[12,000, 98,000]$。我们要映射到 $[0.0, 1.0]$。
    - **问题**: 原始值 $73,600$ 对应的归一化值是多少？
    - **计算**:
        $$\frac{73,600 - 12,000}{98,000 - 12,000}(1.0 - 0) + 0 = 0.716$$
- **优缺点**:
    - _优点_: 保留了原始数据值之间的相对关系。
    - _缺点_: 如果以后输入的新数据超过了原来的 $min/max$（越界），或者遇到**离群点 (Outlier)**，效果会很差。

##### B. Z-分数规范化 (Z-score Normalization / Zero-Mean)

**原理**：基于属性的均值 ($\mu$) 和标准差 ($\sigma$) 进行规范化。
- **公式**:
    $$v' = \frac{v - \mu_A}{\sigma_A}$$
- **PPT 案例**:
    - **已知**: $\mu = 54,000$, $\sigma = 16,000$。
    - **问题**: 原始值 $73,600$ 对应的 Z-score 是多少？
    - **计算**:
        $$\frac{73,600 - 54,000}{16,000} = 1.225$$
- **优缺点**:
    - _优点_: 当**原始的最值 ($min/max$) 未知**，或者存在**离群点**左右最值时，这种方法非常有用（Robust）。

##### C. 小数定标规范化 (Decimal Scaling)
**原理**：通过移动小数点的位置来进行规范化。移动的位数取决于属性绝对值的最大值。
- **公式**:
    $$v' = \frac{v}{10^j}$$
    - $j$ 是使得 $Max(|v'|) < 1$ 的最小整数。
- **PPT 案例**:
    - **已知**: 某属性的值域范围是 $-986$ 到 $917$。
    - **分析**: 绝对值的最大值是 $986$。要让 $986$ 变成小于 $1$ 的小数，需要除以 $1000$ ($10^3$)。所以 $j=3$。
    - **计算**:
        - $-986 \to -0.986$
        - $917 \to 0.917$
#### 🧱 离散化 (Discretization)

**定义**：通过将连续属性的值域划分为若干个区间 (Intervals)，用区间标签来代替实际的数据值。
- **作用**:
    - 减少数据量。
    - 为某些只能处理分类数据的算法（如某些决策树实现）做准备。
- **方法**:
    - **分箱 (Binning)**: Top-down split (自顶向下分裂)。
    - **直方图分析 (Histogram Analysis)**: Top-down split。
    - **聚类分析 (Clustering Analysis)**: Unsupervised (无监督)。
    - **决策树分析 (Decision Tree Analysis)**: Supervised (有监督，利用类标号来划分区间)。
    - **相关分析 (Correlation Analysis)**: Unsupervised。

| **题目特征 / 场景**                     | **推荐方法**            | **关键公式摘要**                  |
| --------------------------------- | ------------------- | --------------------------- |
| **已知 Min, Max，映射到 [0,1]**         | **Min-Max**         | $\frac{v - min}{max - min}$ |
| **已知 Mean, Std Dev，或者有 Outliers** | **Z-score**         | $\frac{v - \mu}{\sigma}$    |
| **只需简单缩小数量级**                     | **Decimal Scaling** | $\frac{v}{10^j}$            |
## Lecture 4

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
