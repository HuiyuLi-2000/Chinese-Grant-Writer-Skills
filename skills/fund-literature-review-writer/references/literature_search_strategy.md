# 文献检索策略

> 本文件是指针文件，将各检索相关内容路由到对应的具体文档，避免重复。
> **不使用**：PubMed、arXiv。**不调用子 agent**。

---

## 检索源一览

| 检索源 | 用途 | 脚本 |
|--------|------|------|
| OpenAlex + Crossref + Exa + Google Scholar | 英文文献（四源并行） | `search/scripts/search_all.py` |
| Zotero MCP | 用户已有文献库 | MCP 工具（可选） |
| 本地文件 | 用户已有 .bib/.pdf | agent 自行扫描（可选） |

---

## 详细内容导航

| 主题 | 位置 |
|------|------|
| 完整搜索工作流（脚本调用链、查询构造、合并去重、降级策略） | `references/fund-search-workflow.md` |
| 文献数量/语言/时效规范、排序权重、筛选优先级 | `config.yaml` 的 `search` 节 |
| BibTeX 输出格式要求 | `config.yaml` 的 `bibtex` 节 |
| 各搜索源 API 调用细节和并行路由 | `search/references/search-strategy.md` |
| OpenAlex / Crossref API 参数速查 | `search/references/api-reference.md` |
| 统一数据结构字段定义 | `search/references/data-schema.md` |
| 期刊层级分类说明 | `search/references/journal-tiers.md` |
