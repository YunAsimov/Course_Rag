**要点概括：**

1. **图数据结构基础 (Graph Data Fundamentals):** 定义了图的数学表示，以及同/异配图 (Homophilic/Heterophilic) 和同/异质图 (Homogeneous/Heterogeneous) 的分类。
2. **传统深度学习的局限 (Limitations of Traditional DL):** 解释了为何多层感知机 (MLP) 和卷积神经网络 (CNN) 无法直接处理图数据，引出了图数据的置换不变性 (Permutation Invariant) 和等变性 (Equivariant) 需求。
3. **图卷积网络 (Graph Convolutional Neural Networks, GCN):** 深入剖析了 GCN 的邻居聚合 (Neighbor Aggregation) 原理，并一步步推导了从加入自环到度矩阵归一化 (Normalization) 的完整矩阵运算过程。
4. **图神经网络的应用 (GNN Applications):** 列举了 GNN 在节点分类 (Node Classification)、链路预测 (Link Prediction) 等任务上的表现，以及在反欺诈、推荐系统和医疗生物领域的实际落地。
5. **可解释性与安全性 (XAI & Robustness):** 探讨了可解释人工智能 (Explainable AI) 的意义，并分析了图结构面临的对抗攻击 (Adversarial Attack) 威胁。

# COMP 5575 Lecture 11: 图神经网络 (Graph Neural Network, GNN)

## 1. 图数据结构基础 (Graph Data Fundamentals) 🕸️

在现实生活中，图结构无处不在（如知识图谱、社交网络等）。图能够有效地表达实体及其相互复杂的关联。

### 1.1 图的数学表达 (Mathematical Expression)

图通常可以抽象表示为 $G = \{V, E, A, X\}$，其中：

- **$V$**: 节点集合 (Vertex/Node set)
- **$E$**: 边集合 (Edge set)
- **$A$**: 邻接矩阵 (Adjacency Matrix)，通常为二值矩阵 (Binary matrix) 以表示节点间是否直接相连
- **$X$**: 节点特征矩阵 (Node Feature Matrix)

### 1.2 图的常见分类 (Types of Graphs)

- **按边和时间特性:** * 有向图 (Directed graph) vs 无向图 (Undirected graph)。
    - 静态图 (Static Graph) vs 动态图 (Dynamic Graph)。对于时序动态图 (Temporal Dynamic Graph)，通常采用基于快照 (Snapshot based) 的时间训练结构进行处理。
- **按节点关系 (Nature of Relationships):**
    - **同配图 (Homophilic Graph):** 连接相似的节点（例如：同一领域的学术论文互相引用）。
    - **异配图 (Heterophilic Graph):** 连接不相似的节点（例如：欺诈者与正常客户之间的联系）。
- **按节点/边种类 (Types of Nodes/Edges):**
    - **同质图 (Homogeneous Graph):** 仅包含一种节点和边。
    - **异质图 (Heterogeneous Graph):** 包含多种实体和关系（例如：学术网络中包含“作者”、“机构”和“论文”等多种维度的节点）。

---

## 2. 为什么需要图神经网络？(Why GNN?) 🧠

传统的深度学习模型在处理图数据时面临着根本性的数学阻碍。图数据属于非欧几里得空间，不能用简单的欧几里得坐标系 (Euclidean Coordinate system) 来表示。

### 2.1 核心需求：置换不变性与等变性

图数据本质上是没有固定绝对顺序的。一个合格的 GNN 必须满足：

- **置换不变性 (Permutation Invariant):** 无论图中的节点如何重新编号（改变输入顺序），整个图的最终表示输出必须保持一致。
- **置换等变性 (Permutation Equivariant):** 改变输入节点的编号顺序，输出的对应节点嵌入 (Node Embedding) 的排列顺序也会相应改变，但每个具体节点的特征向量必须相同。

### 2.2 传统模型的失败尝试

- **多层感知机 (MLP):** MLP 强依赖于输入的绝对位置，对节点顺序极其敏感 (Sensitive to node ordering)，无法保持置换不变性，因此无法提取不规则的图拓扑结构特征。
- **卷积神经网络 (CNN):** CNN 依赖固定的局部性或滑动窗口 (Sliding window)。虽然可以将邻接矩阵强行输入 CNN，但池化层 (Pooling layer) 会破坏图的拓扑结构，无法保证特征池化后还能与正确的节点匹配。

---

## 3. 图卷积神经网络 (Graph Convolutional Neural Network, GCN) ⚙️

GCN 的核心思想是**消息传递 (Message Passing)** 和**邻居聚合 (Neighbor Aggregation)**。模型通过聚合局部邻居节点的信息来生成目标节点的嵌入表示。

### 3.1 GraphSAGE 聚合机制

GraphSAGE 采用平均邻居信息的方式：

1. 第 $0$ 层的节点表示就是它的初始输入特征 $x_v$。
2. 第 $k+1$ 层的节点表示，是通过平均其所有邻居在第 $k$ 层的特征，并与该节点自身的第 $k$ 层特征结合，最后通过非线性激活函数 (Nonlinear function, 如 ReLU 或 Sigmoid) 计算得出。

### 3.2 GCN 矩阵运算推导 (Matrix Formulation of GCN)

这是 GCN 底层计算的核心。整个聚合和更新过程可以通过稀疏矩阵运算 (Sparse matrix operations) 高效完成：

$$H^{k+1} = \sigma(\tilde{A}H^kW_k)$$

**计算步骤拆解：**

1. **加入自环 (Self-connection):** 节点在聚合邻居信息时，不能忽略自身的特征。因此，需要构造包含自转换的增强邻接矩阵 $A_{new} = A + I$ ($I$ 为单位矩阵)。
2. **计算度矩阵 (Degree Matrix):** 统计加上自环后每个节点的邻居数量，构建对角矩阵 $D$。
3. **归一化 (Normalization):** 为了防止拥有大量邻居的节点特征值过度累加，需要对矩阵进行归一化处理。通过计算 $D^{-1}$ 得到归一化邻接矩阵 $\tilde{A} = D^{-1}(A + I)$。
4. **特征聚合与映射:** 用 $\tilde{A}$ 乘以当前隐藏层特征矩阵 $H^k$，完成邻居特征的聚合，然后再乘以当前层的可训练权重矩阵 $W_k$。
5. **激活 (Activation):** 最后通过激活函数 $\sigma$ (例如 Softmax 或 ReLU) 处理，得到下一层的节点表示 $H^{k+1}$。

_(注：如果将运算中的归一化邻接矩阵 $\tilde{A}$ 替换为基于特征动态计算的注意力分数矩阵 (Attention Score Matrix)，GCN 架构就扩展成了**图注意力网络 (Graph Attention Network, GAT)**)。_

---

## 4. GNN 的任务与应用 (Tasks and Applications) 🚀

### 4.1 主要学习任务

- **节点分类 (Node Classification):** 根据节点的属性以及它们之间的关系，预测图中未知节点的标签 (Labels)。
- **链路预测 (Link Prediction):** 预测网络中两个节点之间是否存在缺失的连接或未来是否会产生连接。
- **图分类 (Graph Classification):** 将整个图作为一个整体映射到一个特定的分类标签。

### 4.2 实际落地场景

- **金融反欺诈 (Credit Fraudster Detection):** 欺诈者在交易网络中的交互模式与正常用户存在差异，GNN 能够主动识别这些异常拓扑并做出响应。
- **推荐系统 (Recommender Systems):** 利用协同过滤 (Collaborative Filtering) 原理，基于社区用户的偏好网络进行物品发现和推荐。
- **生物医疗 (Healthcare & Biotech):** * GNN 能够将药物分子 (Molecular graph) 表示为图，保留其结构细节以进行属性预测。
    - 构建疾病网络模型，预测药物反应以助力精准医疗 (Precision Medicine)。
- **检索增强生成 (GNN-RAG):** 结合知识图谱网络，极大提升大语言模型在多实体 (Multi-Entity) 和多跳 (Multi-Hop) 复杂逻辑推理上的能力。

---

## 5. 可解释性与安全性 (XAI & Robustness) 🛡️

### 5.1 可解释人工智能 (Explainable AI, XAI)

当 GNN 被用作黑盒预测时，可能会出现不可预测的错误。引入 XAI 可以帮助我们理解模型得出特定结论的内部原因。主要评估维度包括因果关系 (Causality)、信息量 (Informativeness)、公平性 (Fairness) 以及模型间的可迁移性 (Transferability)。

### 5.2 对抗攻击 (Adversarial Attack)

由于图数据的平台通常具有开放性，攻击者很容易通过**修改节点特征**（如修改用户资料）或**增删边**（如虚假订阅或退订）来发起攻击：

- **逃逸攻击 (Evasion Attack):** 在测试阶段修改图的结构特征，使 GNN 做出错误的预测。
- **投毒攻击 (Poisoning Attack):** 在训练阶段注入恶意图数据（如向推荐系统中注入大量具有特定行为的虚假用户），从而改变模型的推荐权重。