---
name: "fund-literature-review-writer"
description: "撰写NSFC申请书的国内外研究现状及发展动态分析+文献评述。Invoke when user asks to write NSFC literature review, 国内外研究现状, 文献综述, 文献评述, or 1.2部分 of NSFC proposal."
---

# NSFC 文献综述与文献评述写作技能

## 核心定位

本技能不是"写文献"，而是**将文献转化为"NSFC研究论证结构的一部分"**。

在用户已有研究构想基础上，学习NSFC成功项目中的"文献综述—文献评述"组织方式，对文献部分进行学术化重构、逻辑组织优化、批判性归纳、面向NSFC表达体系的规范化输出。

## 触发条件

当用户需要撰写以下内容时触发：
- NSFC申请书的"1.2 国内外研究现状及发展动态分析"
- NSFC申请书的"文献综述"部分
- NSFC申请书的"文献评述"部分
- 用户明确要求"写文献综述"、"写文献评述"、"写研究现状"

## 核心原则

1. **不预设固定结构**：文献综述的结构从16本NSFC成功本子中"学习出来"，不是"写死出来"
2. **不文献摘要堆叠**：禁止文献摘要式输出，文献必须融入论证
3. **不脱离NSFC语境**：文献服务NSFC研究论证结构
4. **强调结构归纳能力**：从本子中归纳组织逻辑，不固化模板
5. **强调批判性评述能力**：文献评述是结构性判断，不是总结
6. **强调文献服务研究问题能力**：文献→研究问题/方法/创新的完整论证链

## 技能范围

本技能只负责 NSFC 申请书中立项依据的 1.2 国内外研究现状及发展动态分析 + 文献评述 部分。需读取用户研究构想以确保文献服务研究论证。

## 知识库引用

执行本技能前，必须读取以下知识库文件：

### knowledge_base/
1. `literature_review_style_guide.md`：文献综述写作风格指南
   - 文献综述的整体叙事逻辑
   - 主题划分策略（4种方式）
   - 段落组织规范（论证功能，非固定句式）
   - 文献引用格式
   - 文献间连接词使用规律
   - 表格使用规范
   - 综述→评述的过渡方式
   - 批判性表达规律
   - 字数规范

2. `literature_review_patterns.md`：文献综述组织逻辑范式
   - 五种项目类型的典型文献综述组织
   - 方法型/机制型/系统型文献组织差异
   - 文献群的构建逻辑
   - 文献→研究问题/方法/创新映射模式
   - 文献评述的4种批判性判断类型
   - 文献组织的选择决策树

3. `literature_mapping_rules.md`：文献→研究问题/方法/创新映射规则
   - 文献→研究问题映射规则
   - 文献→方法合理性映射规则
   - 文献→创新合理性映射规则
   - 与用户研究构想的对齐机制

### references/
1. `info_form.md`：用户输入信息表
2. `output_skeletons.md`：输出骨架（论证功能，非固定模板）
3. `validation_menu.md`：验证菜单
4. `anti_patterns.md`：反模式清单
5. `literature_search_strategy.md`：文献检索策略
6. `fund-search-workflow.md`：完整搜索工作流（脚本调用链、降级策略）

### search/（内化搜索包）
- `search/scripts/`：搜索脚本（search_all.py, citation_finder.py, rank_and_filter.py, format_bibtex.py, dedup.py，另有 tier_utils/exa_search/search_google_scholar 等内部依赖，无需直接调用）
- `search/references/`：搜索参考文档（search-strategy.md, api-reference.md, data-schema.md, journal-tiers.md）
- `search/data/`：期刊数据（priority_journals.csv, blacklist_journals.csv）
- `search/.env.example`：API 密钥模板（需复制为 .env 并填写）
- `search/requirements.txt`：Python 依赖（requests, exa-py, scholarly）

## 工作流程

### Step 1: 理解研究目标
- 读取用户研究构想（研究主题、研究目标）
- 确定文献综述的总体方向

### Step 2: 解析研究内容
- 读取用户研究内容（通常3-5个）
- 确定文献综述的主题划分

### Step 3: 识别关键科学问题
- 读取用户关键科学问题（通常1-3个）
- 确定文献评述的研究空白方向

### Step 4: 检索文献
- 读取 `references/fund-search-workflow.md` 获取完整搜索流程

**4a. 构造主题检索查询**：从研究主题/内容/方法/关键科学问题生成英文查询组

**4b. 英文文献搜索**（四源并行）：
```bash
# 设置环境变量（从 search/.env.example 复制为 search/.env 并填写）
# 对每个英文查询组执行：
python search/scripts/search_all.py --query "{英文查询}" --email "$OPENALEX_EMAIL" --output runs/cf/query_N.json
# 合并所有查询组：
python search/scripts/citation_finder.py merge runs/cf/query_*.json --output runs/cf/merged.json
# 补算期刊层级：
python search/scripts/citation_finder.py enrich-tiers --input runs/cf/merged.json --priority-csv search/data/priority_journals.csv --blacklist-csv search/data/blacklist_journals.csv --output runs/cf/enriched.json
```

**4c. Zotero MCP / 本地文件搜索**（可选）：按 `fund-search-workflow.md` Step 4/5 执行

**4d. 全源合并去重排序**：
```bash
python search/scripts/dedup.py --input runs/all_merged.json --output runs/deduped.json
python search/scripts/rank_and_filter.py --input runs/deduped.json --weights relevance=0.4,journal_tier=0.3,citation_count=0.2,recency=0.1 --output runs/final.json
python search/scripts/format_bibtex.py --input runs/final.json --output runs/nsfc_references.bib
```

### Step 5: 确认文献集合
- 直接使用 Step 4d 输出的 `runs/final.json`（已去重、排序、筛选）
- 如需调整筛选权重或优先级，参见 `references/literature_search_strategy.md`

### Step 6: 自动归纳文献组织方式
- 根据 `literature_review_patterns.md` 选择文献组织方式
- 根据项目类型选择典型组织模式
- 根据研究内容划分文献主题
- 根据研究方法确定方法介绍侧重点

### Step 7: 生成文献综述
- 按 `literature_review_style_guide.md` 和 `output_skeletons.md` 生成文献综述
- 主题划分策略（4种方式，根据研究内容选择）
- 段落组织（论证功能：引入→举例→对比→转折→总结）
- 文献引用格式（作者-年份制优先）
- 表格使用（方法研究型默认使用）
- 嵌入式评述（每个主题段末）

### Step 8: 生成文献评述（独立模块）
- 按 `output_skeletons.md` 生成文献评述
- 评述方式（嵌入式/独立式，根据项目类型选择）
- 批判性判断（方法性/数据适用性/模型解释能力/研究边界）
- 引出本项目研究方向

### Step 9: 校验与用户研究构想一致性
- 按 `validation_menu.md` 逐项验证
- 文献综述与研究内容的一致性检查
- 文献评述与研究问题的对应检查
- 文献→方法→创新的闭环检查
- 引用格式一致性检查
- 字数检查
- 文献质量检查
- 反模式检查（按 `anti_patterns.md`）

## 适配机制

### 用户已有文献
- 优先使用用户已有文献
- 补充检索缺失的文献
- 验证用户文献的质量和相关性

### 用户无文献
- 完全依赖自动检索
- 按 `literature_search_strategy.md` 执行检索
- 生成完整的BibTeX引用库

### 用户部分文献
- 以用户已有文献为基础
- 补充检索缺失的文献
- 确保文献覆盖所有研究内容

## 输出格式

### 输出1：文献综述主体 + 文献评述（MD文件）

```markdown
# 1.2 国内外研究现状及发展动态分析

## 1.2.1 主题1（对应研究内容1）
[引入段]
[子主题1.1 文献群]
[子主题1.2 文献群]
[主题评述段（嵌入式评述）]

## 1.2.2 主题2（对应研究内容2）
[引入段]
[子主题2.1 文献群]
[子主题2.2 文献群]
[主题评述段（嵌入式评述）]

## 1.2.3 主题3（对应研究内容3）
[引入段]
[子主题3.1 文献群]
[子主题3.2 文献群]
[主题评述段（嵌入式评述）]

## 1.2.X 文献评述（独立评述小节，可选）
[开头段]
[主题评述段1]
[主题评述段2]
[主题评述段3]
[总结段]

## 参考文献
[参考文献列表]
```

### 输出2：BibTeX格式引用库

```bibtex
% NSFC申请书文献综述引用库
% 生成时间：YYYY-MM-DD
% 项目主题：XXX

@article{key1,
  title = {文献标题},
  author = {作者},
  journal = {期刊},
  year = {年份},
  doi = {DOI}
}
```

## 引文格式要求

### 正文引用
- **作者-年份制**（优先）：`作者等(年份)` 或 `Author et al.(年份)`
- **编号制**（按用户需求自适应）：`[1]`、`[2]`

### 参考文献输出（唯一格式）
- **BibTeX格式**（强制）
- 必须完整字段（title/author/journal/year）
- 尽可能存留DOI
- 不允许缺失关键信息（如未知需标注）
- 用于 Zotero / BibTeX 直接导入

## 语言约束

- 除了必要的术语、文件名、标题等，使用中文
- 中英文混合引用（中文文献用"姓名等(年份)"，英文文献用"Author等(年份)"）

## 禁止行为

1. ❌ 禁止文献摘要式输出
2. ❌ 禁止简单罗列论文
3. ❌ 禁止时间线式综述
4. ❌ 禁止固定模板化写作（段落/句子模板不允许预设）
5. ❌ 禁止文献与研究主题脱节组织
6. ❌ 禁止文献独立成体系
7. ❌ 禁止文献评述只是总结，无批判性判断
8. ❌ 禁止调用子agent
9. ❌ 禁止使用 PubMed 和 arXiv 检索
10. ❌ 禁止营销类文章、无来源内容、二次转载数据、非学术总结性材料
11. ❌ 禁止使用 claim_extractor.py 和 support_llm.py（逐条声明评估，非本技能用途）
12. ❌ 禁止下载全文（CNKI/ScienceDirect 仅收集元数据，不点 Download/View PDF）

## 最终原则

> 文献综述的结构，应当从NSFC成功本子中"学习出来"，而不是"写死出来"。

文献不是独立成体系，而是服务用户研究构想。每篇文献都应在"文献→研究问题/方法/创新"的论证链中找到位置。
