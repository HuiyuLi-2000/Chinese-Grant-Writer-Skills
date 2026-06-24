# API 速查表

## 目录

- [1. OpenAlex](#1-openalex)
- [2. Crossref](#2-crossref)

---

## 1. OpenAlex

### Works 搜索

| 项目 | 内容 |
|------|------|
| 端点 | `GET https://api.openalex.org/works` |
| 认证 | 无需 key，`mailto=` 进快速池 |
| 限速 | 无 mailto 10 req/s，有 mailto 100 req/s |
| 示例 | `https://api.openalex.org/works?search=transformer+attention&filter=from_publication_date:2020-01-01,type:article&per_page=15&sort=relevance_score:desc&mailto=user@example.com` |

**关键参数**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `search` | 全文搜索 | - |
| `filter` | 过滤条件，逗号分隔 | - |
| `sort` | 排序字段:方向 | relevance_score:desc |
| `per_page` | 每页结果数 | 25，最大50 |
| `cursor` | 游标分页 | - |
| `select` | 返回字段 | 全部 |
| `mailto` | 快速池 | - |

**常用 filter**：

| filter | 说明 | 示例 |
|--------|------|------|
| `from_publication_date` | 起始日期 | `2020-01-01` |
| `to_publication_date` | 截止日期 | `2024-12-31` |
| `type` | 文献类型 | `article`, `conference-paper` |
| `primary_location.source.issn` | ISSN | `0028-0836` |
| `concepts.id` | 概念ID | `https://openalex.org/C41008148` |
| `is_oa` | 是否OA | `true` |
| `has_doi` | 是否有DOI | `true` |

### Sources 查询

| 项目 | 内容 |
|------|------|
| 端点 | `GET https://api.openalex.org/sources` |
| 认证 | 同 Works |
| 限速 | 同 Works |
| 示例 | `https://api.openalex.org/sources?filter=issn:0028-0836` |

**返回字段**：

| 字段 | 说明 |
|------|------|
| `display_name` | 期刊名 |
| `issn_l` | ISSN-L |
| `issn` | ISSN 列表 |
| `type` | 类型（journal/conference等） |
| `host_organization_name` | 出版集团 |
| `summary_stats.2yr_mean_citedness` | 2年均被引率（≈IF） |
| `summary_stats.h_index` | 期刊h指数 |
| `summary_stats.i10_index` | i10指数 |
| `works_count` | 论文总数 |
| `is_in_doaj` | 是否DOAJ |
| `apc_usd` | APC费用 |

---

## 2. Crossref

### Works 搜索

| 项目 | 内容 |
|------|------|
| 端点 | `GET https://api.crossref.org/works` |
| 认证 | 无需 key，`mailto=` 进 polite pool |
| 限速 | 无 mailto 1 req/s，有 mailto 10 req/s |
| 示例 | `https://api.crossref.org/works?query.bibliographic=attention+is+all+you+need&filter=has-abstract:true,type:journal-article|proceedings-article&rows=15&sort=is-referenced-by-count&mailto=user@example.com` |

**关键参数**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 全字段搜索 | - |
| `query.bibliographic` | 标题级搜索 | - |
| `query.title` | 标题搜索 | - |
| `query.author` | 作者搜索 | - |
| `filter` | 过滤条件，逗号分隔 | - |
| `sort` | 排序 | relevance |
| `rows` | 返回数量 | 20，最大1000 |
| `offset` | 分页偏移 | 0 |
| `select` | 返回字段 | 全部 |
| `mailto` | polite pool | - |

**常用 filter**：

| filter | 说明 | 示例 |
|--------|------|------|
| `has-abstract:true` | 有摘要 | - |
| `type:journal-article\|proceedings-article` | 期刊论文+会议论文 | - |
| `from-pub-date` | 起始日期 | `2020-01-01` |
| `until-pub-date` | 截止日期 | `2024-12-31` |
| `issn` | ISSN | `0028-0836` |
| `member` | 出版商ID | - |

### DOI 验证

| 项目 | 内容 |
|------|------|
| 端点 | `GET https://api.crossref.org/works/{doi}` |
| 示例 | `https://api.crossref.org/works/10.1038/s41586-021-03819-2` |

### Journals 查询

| 项目 | 内容 |
|------|------|
| 端点 | `GET https://api.crossref.org/journals/{issn}` |
| 示例 | `https://api.crossref.org/journals/0028-0836` |

**返回字段**：

| 字段 | 说明 |
|------|------|
| `title` | 期刊名 |
| `ISSN` | ISSN列表 |
| `publisher` | 出版商 |
| `subject` | 学科分类 |
| `counts.total-dois` | DOI总数 |
