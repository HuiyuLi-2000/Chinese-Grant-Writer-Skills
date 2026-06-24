# 期刊分级（tier_score）

`tier_score` 是论文综合分的三项之一，衡量发表载体（期刊或会议）的等级。由 `scripts/tier_utils.py:compute_paper_tier_score` 计算，agent 不直接调用——`search_all.py` 内部已自动填充。

本文档说明：评分如何映射、数据从哪来、会议怎么处理、有哪些 caveat。

recency_score、support_score、composite_score 的定义见 [skill.md](../skill.md) Step 3。support_score 详见 [support-grading.md](support-grading.md)。

---

## 0. recency_score 评分表

`recency_score` 衡量论文的时效性，由 `scripts/citation_finder.py:year_normalize` 计算，`search_all.py` 内部已自动填充。

| 年份距今 | recency_score |
|---------|--------------|
| ≤ 2 年 | 1.0 |
| 3-5 年 | 0.8 |
| 6-10 年 | 0.5 |
| 11-20 年 | 0.3 |
| > 20 年 / 无年份 | 0.1 |

---

## 1. 评分表

### 期刊

按 OpenAlex Sources API 返回的 `summary_stats.2yr_mean_citedness`（≈ JCR Impact Factor）分段：

| 2yr_mean_citedness | tier_score | 期刊级别参考 |
|-------------------|------------|-------------|
| > 10 | 0.95 | 顶刊（Nature/Science/Cell 级） |
| 5 - 10 | 0.8 | 强刊（领域顶级） |
| 2 - 5 | 0.6 | 中等（领域主流） |
| 0.5 - 2 | 0.4 | 一般 |
| < 0.5 | 0.2 | 较低 |
| 无数据 | 0.1 | 兜底 |

### 会议

| 情况 | tier_score |
|------|-----------|
| 命中内置白名单（`data/priority_journals.csv`） | 0.8 |
| 未命中白名单，但 OpenAlex 有 citedness | 同期刊评分表 |
| 均无数据 | 0.1 |

---

## 2. 数据来源：OpenAlex Sources

```
GET https://api.openalex.org/sources?filter=issn:{issn}
GET https://api.openalex.org/sources?search={venue_name}
```

期刊：先按 ISSN 查 → 查不到按 venue name 查。会议：先白名单 → 未命中按 venue name 查。所有结果在脚本内缓存（ISSN/name → source），同次运行不重复请求。

**为什么用 `2yr_mean_citedness` 而不是 JCR IF**：JCR 需要 Clarivate 授权，无免费 API；OpenAlex 的指标定义与 JCR 一致，数据源高度重叠（Web of Science），是当前唯一免费、实时、覆盖广的近似方案。中科院分区、SJR、SNIP 同样无免费稳定 API，暂不支持。

完整的 OpenAlex API 端点和参数见 [api-reference.md](api-reference.md)。

---

## 3. 会议白名单

**文件**：`data/priority_journals.csv`

**格式**：

```csv
abbreviation,full_name,category
NeurIPS,Conference on Neural Information Processing Systems,AI/ML
ICML,International Conference on Machine Learning,AI/ML
```

`category` 仅供阅读，代码不使用。

**匹配规则**：venue 与 abbreviation 或 full_name 任一项归一化后（小写 + 去除非字母数字字符）精确匹配或子串包含即命中。

**覆盖**：约 55 个 CCF-A 级 + 领域主流顶会。需要补充时直接编辑 CSV，无需改代码。当前覆盖列表查 CSV 文件本身。

---

## 4. Caveats

- **学科差异**：不同领域 citedness 基线差距大（生医 > CS > 数学），跨学科比较 tier 时需谨慎。
- **新期刊**：发刊不足 2 年时 OpenAlex 无 citedness 数据，会落到 0.1 兜底。
- **会议 citedness 偏低**：会议论文的 OpenAlex citedness 通常低于同级期刊，所以白名单优先于 citedness 兜底。
- **黑名单优先**：列入 `data/blacklist_journals.csv`（MDPI / Frontiers / 中科院预警刊等）的论文在评分前已被过滤，不会进入 tier 评分流程。
