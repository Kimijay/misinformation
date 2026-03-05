# data_by_type/jsonl 字段分析

基于 `data_by_type/jsonl/*.jsonl` 全量统计，不同数据集可以归为两类：

## 1) 用户画像/文本特征类

适用数据集：`train_data`、`train_data_sampled`、`inference_data_1`、`inference_data_2`。

### 统一顶层字段
- `uid` (str)
- `tweet` (list)
- `description` (str)
- `numerical` (list)
- `categorical` (list)
- `label` (int，仅训练集存在)

### 字段完整性与规模

| 数据集 | 记录数 | 字段 |
|---|---:|---|
| train_data | 99,874 | `uid,tweet,description,numerical,categorical,label` |
| train_data_sampled | 48,536 | `uid,tweet,description,numerical,categorical,label` |
| inference_data_1 | 471,215 | `uid,tweet,description,numerical,categorical` |
| inference_data_2 | 471,215 | `uid,tweet,description,numerical,categorical` |

所有上述字段在对应数据集中均为 100% 出现。

### 长度/取值特征
- `numerical` 长度恒为 3。
- `categorical` 长度恒为 20。
- `tweet` 长度：
  - `train_data`: min/avg/max = 0 / 24.65 / 28
  - `train_data_sampled`: min/avg/max = 5 / 5.00 / 5
  - `inference_data_1`: min/avg/max = 0 / 15.52 / 18
  - `inference_data_2`: min/avg/max = 0 / 16.39 / 18
- `description` 空字符串（去空格后）数量：
  - `train_data`: 34,194
  - `train_data_sampled`: 6
  - `inference_data_1`: 223,212
  - `inference_data_2`: 165,326
- `label` 分布：
  - `train_data`: 0 -> 47,760, 1 -> 52,114
  - `train_data_sampled`: 0 -> 30,404, 1 -> 18,132

## 2) 传播图谱/交互行为类

适用数据集：`misinformation`、`verified_information`、`trend_information`。

### 统一顶层字段
- `article` (dict)
- `comment_graphs` (list)
- `repost_graph` (dict)
- `comment_users` (list)
- `repost_users` (list)
- `attitude_users` (list)

以上字段在对应数据集中均为 100% 出现。

### 主要嵌套字段
- `article` 包含：
  - `article_content`
  - `publish_time`
  - `comment_count`
  - `repost_count`
  - `attitude_count`
- `repost_graph` 包含：
  - `nodes`
  - `edges`
- `comment_graphs` 的每个元素通常也是图结构字典，含 `nodes`、`edges`。

### 规模统计

| 数据集 | 记录数 | comment_users(min/avg/max) | repost_users(min/avg/max) | attitude_users(min/avg/max) |
|---|---:|---|---|---|
| misinformation | 7,560 | 0 / 6.58 / 612 | 0 / 14.50 / 24,188 | 0 / 12.52 / 200 |
| verified_information | 8,317 | 0 / 33.88 / 1,344 | 0 / 58.84 / 16,321 | 0 / 42.45 / 200 |
| trend_information | 7,745 | 0 / 22.83 / 1,141 | 0 / 28.57 / 4,760 | 0 / 47.86 / 200 |

补充：`repost_graph.nodes` 与 `repost_graph.edges` 的统计数值一致（min/avg/max 在三个数据集均相同），说明该图在数据中呈现“一条边对应一个节点增量”的近似结构特征。

## 3) 字段层面的结论

1. **可复用的统一 Schema 明确**：
   - 文本特征类 5~6 列（训练含 `label`，推理不含）。
   - 图谱行为类固定 6 列。
2. **训练与推理特征同构**：
   - 推理集字段与训练集除 `label` 外完全一致，适合直接复用特征处理流水线。
3. **空描述占比值得注意**：
   - 在 `train_data` 与两个 `inference_data` 中，`description` 空值并不低，建模时应考虑缺失文本处理策略。
4. **图谱类数据跨度大**：
   - 用户与图节点规模从 0 到上万不等，建议下游对长尾样本做截断或分桶。

## 4) 按你关心的文件名逐个列出字段

> 说明：仓库中部分数据以分片形式存储（`*.part.XXXX`），没有单一同名文件。以下按“逻辑数据集”给出字段。

- `misinformation.jsonl`
  - `article`
  - `comment_graphs`
  - `repost_graph`
  - `comment_users`
  - `repost_users`
  - `attitude_users`

- `trend_information.jsonl`（对应分片：`trend_information.part.*.jsonl`）
  - `article`
  - `comment_graphs`
  - `repost_graph`
  - `comment_users`
  - `repost_users`
  - `attitude_users`

- `verified_information.jsonl`（对应分片：`verified_information.part.*.jsonl`）
  - `article`
  - `comment_graphs`
  - `repost_graph`
  - `comment_users`
  - `repost_users`
  - `attitude_users`

- `inference_data.jsonl`（仓库内对应为 `inference_data_1.part.*.jsonl` 与 `inference_data_2.part.*.jsonl`）
  - `uid`
  - `tweet`
  - `description`
  - `numerical`
  - `categorical`

- `inference_labels.json`（路径：`data_by_type/json/inference_labels.json`）
  - 顶层结构：`{uid: [label, score]}`
  - 因此可理解为字段：
    - `uid`（字典 key）
    - `label`（列表第 1 个元素，int）
    - `score`（列表第 2 个元素，float）

- `train_data_sampled.jsonl`（对应分片：`train_data_sampled.part.*.jsonl`）
  - `uid`
  - `tweet`
  - `description`
  - `numerical`
  - `categorical`
  - `label`

- `train_data.jsonl`（对应分片：`train_data.part.*.jsonl`）
  - `uid`
  - `tweet`
  - `description`
  - `numerical`
  - `categorical`
  - `label`
