# 搜索策略详细文档

## 目录

- [1. 搜索源汇总](#1-搜索源汇总)
- [2. 各搜索源 API 调用细节](#2-各搜索源-api-调用细节)
  - [2.1 OpenAlex](#21-openalex)
  - [2.2 Crossref](#22-crossref)
  - [2.3 Zotero MCP](#23-zotero-mcp)
  - [2.4 本地文献库](#24-本地文献库)
  - [2.5 Exa Search](#25-exa-search)
  - [2.6 Google Scholar](#26-google-scholar)
- [3. 并行搜索路由逻辑](#3-并行搜索路由逻辑)
- [4. 搜索执行流程](#4-搜索执行流程)
- [5. 去重策略](#5-去重策略)

---

## 1. 搜索源汇总

| 搜索源 | 类型 | 优先级 | 执行方式 | 覆盖范围 |
|--------|------|--------|---------|---------|
| OpenAlex | API | 必搜 | `search_all.py` 内部线程 | 2.5亿+文献，跨学科 |
| Crossref | API | 必搜 | `search_all.py` 内部线程 | DOI元数据最权威 |
| Exa Search | Web | 必搜 | `search_all.py` 内部线程 | 全网论文页面补充检索 |
| Google Scholar | Web | 必搜 | `search_all.py` 内部线程 | 最全面（但不稳定） |
| 本地文献库 | 本地 | 可选 | agent 读取指定文件 | 用户指定的本地 .bib/.json 文件 |
| Zotero MCP | 本地 | 优先 | agent 并行调用 MCP 工具 | 用户已有文献 |

---

## 2. 各搜索源 API 调用细节

### 2.1 OpenAlex

**脚本路径**：`scripts/citation_finder.py`（`search_openalex` 函数）

**搜索方式**：通过 OpenAlex Works API 搜索，参数和返回字段详见 [api-reference.md](api-reference.md)

**搜索逻辑**：

```
1. 必搜，始终执行

2. 搜索：GET /works，参数详见 api-reference.md

3. 结果处理：
   - 脚本直接输出统一数据结构 JSON，source_layer: "api", source: "openalex"
   - 摘要从 abstract_inverted_index 还原
   - venue_type 根据 type 字段映射（article→journal, conference-paper→conference, preprint→preprint）
```

---

### 2.2 Crossref

**脚本路径**：`scripts/citation_finder.py`（`search_crossref` 函数）

**搜索方式**：通过 Crossref Works API 搜索，参数和返回字段详见 [api-reference.md](api-reference.md)

**搜索逻辑**：

```
1. 必搜，始终执行

2. 搜索：GET /works，参数详见 api-reference.md

3. 结果处理：
   - 脚本直接输出统一数据结构 JSON，source_layer: "api", source: "crossref"
   - JATS 标签自动从摘要中清除
   - venue_type 根据 type 字段映射（journal-article→journal, proceedings-article→conference, book-chapter→book）
```

---

### 2.3 Zotero MCP

**搜索方式**：通过 Zotero MCP 工具搜索本地文献库

**必需条件**：Zotero MCP 已配置并可用

**可用操作**（具体工具名取决于 MCP 安装版本）：

| 功能 | 说明 |
|------|------|
| 搜索文献 | 按关键词搜索 Zotero 文献库 |
| 获取详情 | 获取文献元数据（标题、作者、DOI 等） |
| 获取全文 | 获取文献全文内容 |
| 获取笔记/标注 | 获取用户标注和笔记 |
| 导出 BibTeX | 导出 BibTeX 格式引用 |

**搜索逻辑**：

```
1. 检测 MCP 可用性：
   → 可用：继续搜索
   → 不可用：静默跳过，最后告知用户

2. fulltext 搜索：
   使用 mcp_zotero-mcp_search_library 工具
   参数：fulltext={claim原文}, fulltextMode="both", limit=10, mode="standard"
   直接用 claim 原文作为查询，不提取关键词

3. 提取元数据：
   从返回结果中提取 title/authors/year/doi/venue/abstract
   按 data-schema.md 统一字段格式写入 zotero_N.json

4. 合并去重：
   调用 citation_finder.py merge 合并到 claim_N.json
   merge 子命令自动去重 + 补算 tier/recency
```

**异常处理**：MCP 不可用时静默跳过，最后告知用户，不影响其他搜索源

---

### 2.4 本地文献库

**支持格式**：

| 格式 | 搜索方式 | 匹配字段 |
|------|---------|---------|
| BibTeX | 解析 .bib 文件 | title, author, keywords, abstract |
| JSON | 解析搜索脚本输出 | title, abstract, doi |

**搜索逻辑**：

```
1. 检测本地文献库路径：
   - 用户指定路径（--local-dirs）
   - 默认路径：papers/, literature/

2. 扫描文件：
   - 扫描 .bib, .json 文件

3. 匹配方式：
   - 关键词子串匹配（查询词拆分后，命中数 ≥ 1/3 即视为匹配）

4. 标记为"已有文献"，优先推荐
```

---

### 2.5 Exa Search

**脚本路径**：`scripts/exa_search.py`

**搜索方式**：通过 `exa-py` SDK（`pip install exa-py`），直接输出 citation-finder 统一数据结构

**必需条件**：无（`.env` 已配置 `EXA_API_KEY`，`exa-py` 已安装）

**CLI 命令**：

```bash
python scripts/exa_search.py search "{核心术语}" --max 10 --category "research paper"
python scripts/exa_search.py search "{核心术语}" --include-domains "arxiv.org,doi.org,openalex.org"
python scripts/exa_search.py search "{核心术语}" --content text --max-chars 8000 --start-date 2020-01-01
```

**关键参数**：

| 参数 | 说明 | 示例 |
|------|------|------|
| `query` | 搜索关键词 | `transformer attention mechanism` |
| `--category` | 内容类别 | `"research paper"`, `"company"`, `"news"` |
| `--content` | 返回内容类型 | `highlights`（默认）, `text`, `summary`, `none` |
| `--max` | 最大结果数 | `10` |
| `--include-domains` | 域名过滤（逗号分隔） | `"arxiv.org,huggingface.co"` |
| `--exclude-domains` | 排除域名 | `"wikipedia.org"` |
| `--type` | 搜索类型 | `auto`（默认）, `neural`, `fast`, `instant` |
| `--start-date` / `--end-date` | 日期过滤 | `2020-01-01`（ISO 8601） |
| `--max-chars` | 内容最大字符数 | `4000`（默认） |

**搜索逻辑**：

```
1. 必搜，始终执行

2. 搜索：
   python scripts/exa_search.py search "{核心术语}" --category "research paper" --max 10

3. 结果处理：
   - 脚本直接输出统一数据结构 JSON 数组，source_layer: "web"
   - agent 收集输出后直接进入合并去重阶段，无需格式转换
```

---

### 2.6 Google Scholar

**脚本路径**：`scripts/search_google_scholar.py`

**搜索方式**：通过 [`scholarly`](https://github.com/scholarly-python-package/scholarly) 库（`pip install scholarly`）— HTTP 请求模拟浏览器访问 Google Scholar

**必需条件**：无（`scholarly` 已安装）

**限速规则**：易被反爬，每次请求后 sleep 2-5秒随机延迟

**CLI 命令**：

```bash
python scripts/search_google_scholar.py "{核心术语}" --limit 20 \
  --year-start 2020 --sort-by relevance

python scripts/search_google_scholar.py "{核心术语}" --limit 20 \
  --sort-by citations --year-start 2018 --year-end 2024 --use-proxy
```

**搜索逻辑**：

```
1. 必搜，始终执行

2. 搜索：
   - search_google_scholar() 函数执行搜索
   - 每次请求后 sleep 2-5秒随机延迟（防反爬）
   - 可选 --use-proxy 降低被封概率

3. 提取字段：
   - 标题、作者、年份、引用数、venue、摘要、DOI/URL

4. 结果处理：
   - 直接输出 citation-finder 统一数据结构 JSON，source_layer: "web"
   - 用 Crossref/OpenAlex 补全期刊、ISSN 等缺失元数据

5. 限制：每个声明最多触发1次
```

**已知风险**：
- `scholarly` 与 Google Scholar 页面结构耦合，Google 更新页面后需升级库
- 频率过高可能触发 CAPTCHA 或临时封禁
- 不保证稳定性，如遇 CAPTCHA 或封禁可使用 `--use-proxy`

---

## 3. 并行搜索路由逻辑

并行逻辑由 `search_all.py` 在 Python 层面保证，agent 只需对每个声明调用一次脚本 + 并行调 Zotero MCP。详见 `skill.md` Step 2 的架构说明。

**六源定义**：

| # | 搜索源 | 执行位置 | 执行方式 |
|---|--------|---------|----------|
| 1 | OpenAlex | search_all.py 内部 | 必搜 |
| 2 | Crossref | search_all.py 内部 | 必搜 |
| 3 | Exa Search | search_all.py 内部 | 必搜 |
| 4 | Google Scholar | search_all.py 内部 | 必搜 |
| 5 | 本地文件库 | search_all.py 内部 | 必搜 |
| 6 | Zotero MCP | agent 并行调用 | MCP 可用则执行 |

**领域提示**：不同领域可调整 query 词和过滤条件，但不改变并行策略。

| 声明领域 | query 侧重点 | 过滤提示 |
|---------|--------------|----------|
| 计算机科学 | 方法名、任务名、benchmark | 可优先关注 conference/preprint |
| 生物医学 | 疾病、机制、干预、结果指标 | 可加入 biomedical / clinical 等限定词 |
| 社会科学 | 构念、样本、因果关系 | 可保留更宽年份窗口 |
| 工程/应用 | 应用场景、材料/系统、性能指标 | 可加入 application / evaluation |
| 跨学科 | 核心对象 + 领域限定词 | 保持全源并行补充 |

---

## 4. 搜索执行流程

### Step 1: search_all.py 并行搜索

```
输入：声明的搜索查询
执行：python scripts/search_all.py --query "{查询}" --email ... --output claim_N.json
脚本内部并行：
  线程1: OpenAlex + Crossref（citation_finder.py，skip_dedup=True）
  线程2: Exa Search（exa_search.py）
  线程3: Google Scholar（search_google_scholar.py）
  线程4: 本地文件扫描（papers/, literature/）
输出：去重 + 避雷过滤 + 补算 tier/recency 后的统一 JSON
```

### Step 1b: Zotero MCP 并行搜索（agent 端）

```
与 search_all.py 同时执行：
  mcp_zotero-mcp_search_library(q="{查询}")
输出：Zotero 本地文献结果
→ agent 合并后可用 enrich-tiers 补算 tier/recency
```

### Step 2: 摘要验证与支撑度评估

```
输入：候选论文列表
执行：
  1. 获取摘要文本（从 API 返回中提取）
  2. 比对摘要与声明内容
  3. 评估支撑度（strong/partial/background/contradictory/unverified）
     - LLM 评估（USE_LLM_SUPPORT=true）：调用 support_llm.py
     - agent 评估：人工比对摘要与声明
  4. 排除标题相关但内容不支撑的论文
输出：带支撑度标签的候选列表
```

---

## 5. 去重策略

### 5.1 去重键

优先级从高到低：

| 去重键 | 匹配方式 | 可靠度 |
|--------|---------|--------|
| DOI | 精确匹配（大小写不敏感） | 最高 |
| 标题 | 归一化后精确匹配 | 中 |

### 5.2 去重流程

```
1. 第一轮：DOI 去重
   - 提取所有候选论文的 DOI
   - 按 DOI 分组，同一 DOI 保留元数据最完整的记录
   - 合并不同来源的补充信息

2. 第二轮：标题去重
   - 标题归一化：小写、去标点、去空格
   - 归一化后精确匹配的论文合并

3. 合并策略：
   - 保留最完整的元数据
   - 记录所有来源（source 字段）
   - 保留最高的 citation_count
```

### 5.3 来源合并优先级

当同一论文从多个来源获取时，字段合并优先级详见 [data-schema.md](data-schema.md) 的"来源合并优先级"表。
