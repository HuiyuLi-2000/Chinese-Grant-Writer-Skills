---
name: "fund-background-writer"
description: "Writes NSFC grant justification research significance section. Invoke when user asks to write 立项依据/研究意义/项目背景 for NSFC or similar grants, or provides a research topic and wants background text."
---

# fund-background-writer

> 基于 16 本成功 NSFC 申请书提炼的写作范式，实现"主题分析 → 政策调研 → 数据调研 → 立项依据撰写"的自动化流程。

## 技能范围

本技能**只负责** NSFC 申请书中立项依据的 **1.1 研究意义** 部分，包含：
- 研究背景（含国家战略、现实困境、学术问题、本项目方案）
- 理论意义
- 实践意义

## 触发条件

当用户要求撰写 NSFC 立项依据、研究意义、项目背景，或提供研究主题并要求生成立项依据时，激活本技能。

---

## 执行流程

收到用户提供的材料后，严格按以下 7 步执行：

用户**至少**会提供以下输入：研究内容、研究方法、技术路线、特色与创新、研究目标、关键科学问题。如果输入不足，**必须先追问补全**再继续。

### Step 1：读取知识库

读取以下文件，学习写作范式：
- `assets/templates/writing_style_guide.md` —— 风格规范和叙事逻辑
- `assets/templates/structure_template.md` —— 段落安排和句子逻辑角色

### Step 2：主题分析

1. 解析研究主题的核心关键词
2. 识别所属学科领域（管理科学与工程 / 医学 / 经济学 / 信息科学等）
3. 确定科学问题属性（鼓励探索 / 聚焦前沿 / 需求牵引 / 交叉融通）

### Step 3：输入-背景锚定

**映射原则**：让 agent 知道背景的每一段要"指向"什么，确保逻辑贯通。锚定是逻辑层面的"影子对应"，不是文字层面的"复制粘贴"——背景中的困境/不足/方案要用背景自己的语言和论证视角来写，但逻辑上要能追溯到后续输入。

**输入→段落映射表**：

| 用户输入 | 对应背景段落 | 写作视角转换 |
|---|---|---|
| 研究内容 | 段落C 的困境条数 | "现实问题"视角，不用"研究内容"视角 |
| 研究方法细节 | 段落D 的不足条数 | "现有方法的局限"视角，不用"本研究方法"视角 |
| 技术路线 | 段落E 的方案展开顺序 | 浓缩为"做什么"不说"怎么做"，用"本项目拟……" |
| 特色与创新 | 理论意义的条目 | 创新点说"做了什么"，理论意义说"有什么学术价值" |
| 研究目标 | 实践意义的条目 | 研究目标说"要实现什么"，实践意义说"对社会/行业有什么价值" |
| 关键科学问题 | 段落F 的科学问题列举 | 进行轻微改写，但不要直接复制，且与后续输入表述接近合理 |

**独立约束**：段落A和B（政策背景+数据背景）不受后续输入约束，由联网检索结果决定。

### Step 4：联网检索

按以下策略执行联网搜索（由 agent 自行选择可用工具）：

#### 政策检索（详见 `references/policy_search_strategy.md`）
- 优先来源：国务院、科技部、NSFC、国家统计局、教育部、国家卫健委、工信部、国家发改委及研究主题对应主管部门
- 目标：找到 2-3 个与主题直接相关的国家/部门级政策文件
- 记录：政策名称、发布年份、核心要求/表述

#### 数据检索（详见 `references/data_search_strategy.md`）
- 优先来源：国家统计局、行业蓝皮书、权威白皮书、国际组织报告、高水平综述
- 目标：找到 3-5 个支撑问题严重性的统计数据
- 记录：年份 + 具体数值 + 出处 + 原始链接
- **禁止**使用营销文章、无来源数据、转载数据

### Step 5：生成立项依据大纲

按 `structure_template.md` 的段落结构，生成大纲：
- 每段标注：写什么、用什么数据/政策、句子逻辑角色
- 确保问题-方案一一对应
- 向用户展示大纲，确认后进入撰写

### Step 6：撰写完整立项依据

严格遵循 `writing_style_guide.md` 的风格规范：
- 按段落 A→B→C→D→E→F → 理论意义 → 实践意义的顺序撰写
- 每段确保有政策/数据支撑
- 理论意义用"动词+对象+价值"结构分点阐述
- 实践意义从宏观到微观层层递进
- 避免"首次""填补空白"等绝对化表述
- 方法术语只做背景/验证手段，不撑段落主线

### Step 7：自检与输出

1. 按 `references/dod_checklist.md` 检查结构完整性
2. 按 `references/boastful_expression_guidelines.md` 排查浮夸表达
3. 按 `references/dimension_coverage_design.md` 检查四个维度覆盖
4. 输出最终文本，同时附上：
   - **使用的政策清单**（政策名称 + 年份 + 核心表述）
   - **使用的统计数据清单**（数据项 + 年份 + 数值 + 出处 + 链接）

---

## 参考文件索引

| 文件 | 用途 |
|------|------|
| `assets/templates/writing_style_guide.md` | 写作风格指南（叙事逻辑、段落安排、句子逻辑角色、风格规范） |
| `assets/templates/structure_template.md` | 立项依据结构模板（段落-句子逻辑骨架） |
| `references/info_form.md` | 最小信息表（必填字段缺失时先追问） |
| `references/scientific_question_guidelines.md` | 科学问题写作要点 |
| `references/scientific_hypothesis_guidelines.md` | 科学假设写作要点 |
| `references/boastful_expression_guidelines.md` | 禁用浮夸表达清单 |
| `references/dimension_coverage_design.md` | 维度覆盖检查设计 |
| `references/theoretical_innovation_guidelines.md` | 理论创新导向指南 |
| `references/dod_checklist.md` | Definition of Done 检查清单 |
| `references/methodology_term_examples.md` | 方法学术语误用对比示例 |
| `references/policy_search_strategy.md` | 政策检索策略 |
| `references/data_search_strategy.md` | 数据检索策略 |
