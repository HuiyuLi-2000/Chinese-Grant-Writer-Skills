# 统一数据结构

所有搜索源的结果必须转换为以下统一格式后再合并。字段设计覆盖 APA/MLA/Chicago/Vancouver/GB-T7714 等主流引文格式所需信息。

## 完整字段定义

```json
{
  "title": "string",
  "authors": ["Last, First", "..."],
  "year": 2024,
  "doi": "10.xxxx/xxxxx or null",
  "venue": "journal or conference name",
  "venue_type": "journal | conference | preprint | book | thesis | other",
  "issn_l": "xxxx-xxxx",
  "issn": ["xxxx-xxxx"],
  "volume": "string",
  "issue": "string",
  "pages": "string",
  "publisher": "string",
  "abstract": "string",
  "citation_count": 0,
  "url": "string",
  "open_access_pdf": "string or null",
  "is_oa": false,
  "oa_status": "string or null",
  "language": "en",
  "keywords": ["string"],
  "source_layer": "api | local | web",
  "source": "openalex | crossref | exa | google_scholar | local_file | zotero",
  "tier_score": 0.0,
  "recency_score": 0.0,
  "support_score": null,
  "support_reasoning": null,
  "composite_score": null
}
```

## 字段说明

| 字段 | 必填 | 来源 | 说明 |
|------|------|------|------|
| title | ✅ | 所有层 | 论文标题 |
| authors | ✅ | 所有层 | 作者列表，格式 `Last, First` |
| year | ✅ | 所有层 | 发表年份 |
| doi | 推荐 / 强推荐，允许 null | API/本地/Web | DOI 标识符；API/本地结果强推荐，Web 层可缺失 |
| venue | ✅ | 所有层 | 期刊/会议/预印本名称 |
| venue_type | ✅ | 所有层 | 类型分类 |
| issn_l | 推荐 | API/本地 | ISSN-L |
| issn | 推荐 | API/本地 | ISSN 列表 |
| volume | 推荐 | API/本地 | 卷号 |
| issue | 推荐 | API/本地 | 期号 |
| pages | 推荐 | API/本地 | 页码范围（如 "583-589"） |
| publisher | 可选 | API/本地 | 出版商 |
| abstract | 推荐 | API/本地 | 摘要，支撑度评估必需 |
| citation_count | 推荐 | API | 被引次数 |
| url | 推荐 | 所有层 | 论文链接 |
| open_access_pdf | 可选 | API | OA PDF 链接 |
| is_oa | 可选 | API | 是否开放获取 |
| oa_status | 可选 | API | OA 状态标签（gold/green/bronze/hybrid 等） |
| language | 可选 | API | 论文语言 |
| keywords | 可选 | API/本地 | 关键词 |
| source_layer | ✅ | 系统填充 | 结果来源层：api/local/web |
| source | ✅ | 系统填充 | 具体来源：openalex/crossref/exa/google_scholar/local_file/zotero |
| tier_score | ✅ | 脚本 | 期刊等级评分（搜索阶段填充） |
| recency_score | ✅ | 脚本 | 时效性评分（搜索阶段填充） |
| support_score | ✅ | LLM/agent | 支撑度评分（评分阶段填充） |
| support_reasoning | 可选 | LLM | 支撑度评分理由（评分阶段填充） |
| composite_score | ✅ | 脚本 | 综合分（评分阶段填充） |

## 各层结果转换规则

| 层 | 来源 | 处理方式 |
|----|------|---------|
| API | openalex / crossref | `search_all.py` 直接输出，已含 tier_score/recency_score |
| Web | exa / google_scholar | `search_all.py` 内部统一格式，已含 tier_score/recency_score |
| 本地 | local_file | `search_all.py` 内部统一格式，已含 tier_score/recency_score |
| 本地 | zotero | agent 从 MCP 返回值提取，缺失字段填 null，`source_layer: "local"`，tier_score/recency_score 初始为 0.0（合并后由 enrich-tiers 补算） |

## 来源合并优先级

当同一论文从多个来源获取时，字段合并优先级：

| 字段 | 优先来源 |
|------|---------|
| DOI | Crossref（最权威） |
| 标题 | Crossref > OpenAlex |
| 作者 | Crossref > OpenAlex |
| 期刊名 | Crossref > OpenAlex |
| 摘要 | Crossref > OpenAlex |
| 引用数 | OpenAlex（cited_by_count）> Crossref |
| ISSN | Crossref > OpenAlex |
