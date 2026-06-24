# NSFC 基金文献搜索工作流

> 本文件定义 NSFC 文献综述的完整搜索流程。搜索脚本和参考文件位于本技能的 `search/` 目录。
> **不使用**：PubMed、arXiv
> **不调用子 agent**

---

## 一、搜索定位：主题聚类 vs 逐条支撑

本技能的搜索目标与 citation-finder 的原始设计不同：

| 维度 | citation-finder（原始） | 本技能（NSFC 文献综述） |
|------|----------------------|------------------------|
| 目标 | 为某个具体 claim 寻找支撑文献 | 为研究主题构建文献群 |
| 查询单位 | 单个声明 | 主题 + 子主题 + 方法 + 局限 |
| 输出 | 带支撑度标签的候选列表 | 按主题分组的文献集合 |
| 排序维度 | 支撑度 > 相关性 > 引用数 | 相关性 > 期刊层级 > 引用数 > 时效性 |

因此，本技能不使用逐条声明的支撑度评估功能。

---

## 二、搜索执行流程

### Step 1: 构造主题检索查询

从用户的研究构想中提取：
- 研究主题（核心领域）
- 研究内容 1~N（对应综述的子主题）
- 研究方法（方法论关键词）
- 关键科学问题（局限性/空白方向）

为每个维度生成英文查询组：

```
主题: "{topic}" AND review
内容1: "{content_1}" AND method
内容1局限: "{content_1}" AND limitation OR gap
内容2: "{content_2}" AND method
内容2局限: "{content_2}" AND limitation OR gap
方法: "{method}" AND recent advances
方法局限: "{method}" AND challenges OR bottleneck
```

### Step 2: 英文文献搜索

脚本位置：`search/scripts/`

**执行顺序**：

1. 设置环境变量（从 `search/.env.example` 复制为 `search/.env` 并填写）：
   - `OPENALEX_EMAIL`（OpenAlex 快速池）
   - `EXA_API_KEY`（Exa Search）
   - `SERPAPI_KEY` 或 `SCHOLARLY_PROXY`（Google Scholar，可选）

2. 对每个英文查询组执行并行搜索：
   ```bash
   python search/scripts/search_all.py \
     --query "{英文查询}" \
     --email "$OPENALEX_EMAIL" \
     --output runs/cf_results/query_N.json
   ```
   `search_all.py` 内部并行调用 OpenAlex、Crossref、Exa、Google Scholar 四个源。

3. 合并所有查询组结果：
   ```bash
   python search/scripts/citation_finder.py merge \
     runs/cf_results/query_*.json \
     --output runs/cf_merged/all_candidates.json
   ```

4. 补算期刊层级和时效性：
   ```bash
   python search/scripts/citation_finder.py enrich-tiers \
     --input runs/cf_merged/all_candidates.json \
     --priority-csv search/data/priority_journals.csv \
     --blacklist-csv search/data/blacklist_journals.csv \
     --output runs/cf_merged/all_enriched.json
   ```

5. 排序和过滤：
   ```bash
   python search/scripts/rank_and_filter.py \
     --input runs/cf_merged/all_enriched.json \
     --weights relevance=0.4,journal_tier=0.3,citation_count=0.2,recency=0.1 \
     --output runs/cf_final/ranked.json
   ```

6. 格式化 BibTeX：
   ```bash
   python search/scripts/format_bibtex.py \
     --input runs/cf_final/ranked.json \
     --output runs/cf_final/references.bib
   ```

### Step 3: Zotero MCP 搜索（可选）

如果 Zotero MCP 可用，用研究主题关键词直接查询用户已有文献库：
```
mcp_zotero-mcp_search_library(q="{主题关键词}", fulltextMode="both", limit=10, mode="standard")
```
提取元数据后，用 `citation_finder.py enrich-tiers` 补算层级信息。

### Step 4: 本地文件搜索（可选）

在用户指定目录搜索 `.bib`、`.json`、`.pdf` 文件，关键词子串匹配后提取元数据。

### Step 5: 全源合并、去重、排序

1. 将所有来源的 JSON 合并到一个列表
2. 去重（DOI 优先，其次标题归一化匹配）：
   ```bash
   python search/scripts/dedup.py \
     --input runs/all_sources_merged.json \
     --output runs/all_deduped.json
   ```
3. 排序（NSFC 权重：相关性 40% + 期刊层级 30% + 引用数 20% + 时效性 10%）
4. 按主题分组输出候选文献集合

### Step 6: 格式化 BibTeX 输出

```bash
python search/scripts/format_bibtex.py \
  --input runs/all_deduped.json \
  --output runs/nsfc_references.bib
```

---

## 三、NSFC 排序权重

| 维度 | 权重 | 说明 |
|------|------|------|
| 相关性 | 40% | 与研究主题/内容的匹配度 |
| 期刊层级 | 30% | 优先期刊 > 普通期刊 > 黑名单期刊 |
| 引用数 | 20% | 高被引论文优先 |
| 时效性 | 10% | 近 3 年论文优先 |

---

## 四、降级策略

| 场景 | 降级方案 |
|------|---------|
| Exa API 不可用 | 跳过 Exa，仅用 OpenAlex + Crossref + Google Scholar |
| Google Scholar 被封 | 加 `--use-proxy` 或跳过，仅用 API 源 |
| Zotero 不可用 | 跳过 Zotero MCP，仅用 citation-finder |
| 文献数量不足 | 扩展同义词，增加查询组 |
| 英文文献不足 | 增加近义查询、放宽年份 |

---

## 五、搜索脚本速查

| 脚本 | 用途 | 位置 |
|------|------|------|
| `search_all.py` | 多源并行搜索（OpenAlex + Crossref + Exa + Google Scholar） | `search/scripts/` |
| `citation_finder.py` | 合并、enrich-tiers、主入口 | `search/scripts/` |
| `rank_and_filter.py` | 排序和过滤 | `search/scripts/` |
| `format_bibtex.py` | BibTeX 格式化 | `search/scripts/` |
| `dedup.py` | 去重 | `search/scripts/` |
| `tier_utils.py` | 期刊层级工具 | `search/scripts/` |
| `exa_search.py` | Exa 单独搜索 | `search/scripts/` |
| `search_google_scholar.py` | Google Scholar 单独搜索 | `search/scripts/` |

---

## 六、详细参考文档

搜索源的技术细节见本技能内化的参考文件：

- `search/references/search-strategy.md`：各搜索源 API 调用细节、并行路由逻辑、去重策略
- `search/references/api-reference.md`：OpenAlex / Crossref API 速查表
- `search/references/data-schema.md`：统一数据结构字段定义
- `search/references/journal-tiers.md`：期刊层级分类说明
- `search/.env.example`：API 密钥模板
- `search/data/priority_journals.csv`：优先期刊列表
- `search/data/blacklist_journals.csv`：黑名单期刊列表
