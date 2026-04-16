---
name: paper-deep
description: This skill should be used when the user asks to "deep analyze paper", "full paper review", "critical assessment", "detailed paper analysis", or "technical deep dive". Use for complete analysis with problem definition, method details, experiments, and critical assessment.
version: 1.0.0
---

# Paper Deep Analysis

## LANGUAGE RULE
**输出语言**: 中文（分析内容）+ 英文（标题/作者/术语/公式）
- **中文**: Abstract Summary, Problem & Motivation, Method, Experiments 分析, Critical Assessment, Connections
- **英文**: Metadata, 论文标题, 专业术语, 数学公式, 代码

## Output Template

```markdown
# [Paper Title] — Deep Analysis

## Metadata
- **Authors**: [First Author]¹, [Second Author]², ...
- **Affiliations**: ¹[University], ²[Company]
- **Venue**: [Conference/Journal], [Year]
- **arXiv**: [XXXX.XXXXX] | **PDF**: [URL]
- **Code**: [GitHub URL, if available]

### Open Source
- **[OPEN]**: GitHub URL with content details (Code / Data / Both)
- **[CLOSED]**: No code or data available
- **[PENDING]**: Authors mention release but not yet available

## Abstract Summary
[2-3 sentence summary in Chinese]

## Problem & Motivation

### Gap
[What problem exists with prior research? Why are current methods insufficient?]

### Goal
[Specific problem this paper aims to solve]

### Challenges
[Technical difficulties in solving this problem]

## Method

### Core Innovation
[One-sentence summary of core innovation]

### Architecture
[Text or diagram describing architecture]

#### Key Figures
[在分析过程中，识别并嵌入关键图片。图片选择标准：
- 对理解方法本质至关重要（如架构图、流程图）
- 展示核心实验结果
- 包含重要对比或消融分析

使用 `![](images/xxx.jpg)` 语法嵌入图片，图片后可附带简短说明。
注意：根据论文实际情况灵活判断，非强制要求]

### Key Components

#### Component 1: [Name]
[Purpose + implementation key points]

#### Component 2: [Name]
[Purpose + implementation key points]

### Training Objective
[Loss function or optimization objective]

## Experiments

### Datasets
| Dataset | Train | Test | Domain |
|---------|-------|------|--------|
| [...]   | [...] | [...] | [...] |

### Baselines
- [方法1]: [简要说明]
- [方法2]: [简要说明]

### Metrics
[主要评估指标]

### Main Results
| Method | [指标1] | [指标2] | Notes |
|--------|---------|---------|-------|
| Ours   | [...]   | [...]   | [...] |
| SOTA   | [...]   | [...]   | [...] |

#### Key Figures
[在此嵌入实验结果相关的关键图片：
- 主要结果对比图
- 消融分析结果图
- 可视化分析图

使用 `![](images/xxx.jpg)` 语法嵌入，图片后附带结果说明。]

### Ablation Study
[各组件贡献的分析结果]

### Analysis
[作者提供的额外分析：案例分析、可视化等]

## Critical Assessment

### Strengths
- [优点1]
- [优点2]

### Weaknesses
- [缺点1]
- [缺点2]

### Limitations (Author-admitted)
[作者承认的局限性]

### Questions Left Open
- [未解决问题1]
- [未解决问题2]

## Connections

### Builds On
- [论文标题](arxiv:XXXX.XXXXX) — [关系]

### Competes With
- [论文标题](arxiv:XXXX.XXXXX) — [同一问题的不同方法]

### Related Work
- [方向1]: 相关论文和方向
- [方向2]: 相关论文和方向

### Keywords
[tag1] [tag2] [tag3] ...

---
*Analyzed: [日期]*
```

## Key Points

### Problem & Motivation Section
- **Gap**: Limitations of existing methods, why new approach is needed
- **Goal**: Clear problem definition
- **Challenges**: Technical difficulties

### Method Section
- **Core Innovation**: Summarize core innovation in one sentence
- **Architecture**: High-level architecture description, don't get lost in details
- **Key Components**: Purpose and key design of each core module

### Experiments Section
- **Datasets**: Include train/test split and domain
- **Baselines**: List comparison methods and their characteristics
- **Main Results**: Present in table format, highlight vs SOTA differences
- **Ablation Study**: Contribution of each component

### Critical Assessment Section
- **Strengths**: New problem/new method/significant improvement/open source contribution
- **Weaknesses**: Data limitations/incomplete baselines/computational cost/overclaimed
- **Limitations**: Limitations admitted by authors
- **Questions Left Open**: Unresolved issues, future directions

### Connections Section
- **Builds On**: Directly based on which works
- **Competes With**: Competing methods
- **Related Work**: Related directions and papers
- **Keywords**: Tags for easy retrieval

## Reading Framework

### Core Questions (Always ask yourself when reading)
1. **What?** What did this paper do?
2. **So what?** Why does it matter? What gap does it solve?
3. **Now what?** What can I learn? How to apply?

### Paper Structure Analysis

**Abstract Close Reading** (5-sentence method):
- Sentences 1-2: Problem + Gap
- Sentence 3: Method core idea
- Sentence 4: Key results
- Sentence 5: Conclusion/impact

**Introduction Key Sentence Identification**:
- "However, existing methods..." → Find gap
- "To address this, we propose..." → Find solution
- "Our key insight is..." → Find insight
- "Unlike prior work..." → Find differences

**Method Architecture Hierarchy**:
```
High-level idea → Core components → Implementation details → Training objective
```

**Experiments Review Checklist**:
- [ ] Datasets: train/test split? Pretraining data?
- [ ] Baselines: Fair comparison? SOTA included?
- [ ] Metrics: Are metrics reasonable? Gaming metrics?
- [ ] Implementation: Hyperparameters? Compute resources?
- [ ] Ablation: Contribution of each component?
- [ ] Case studies: Qualitative supports quantitative?

### Critical Thinking Red Flags (Watch out for)
- Claims "State-of-the-art" but incomplete baselines
- Only reports best metrics, not average
- Small dataset but claims generality
- Insufficient ablation studies
- No error analysis
- Overclaimed, insufficient evidence

### Paper Type Differences
| Type | Focus | Output Emphasis |
|------|-------|-----------------|
| Empirical | Are experiments fair? Ablation sufficient? Reproducible? | Key results, Ablation findings |
| Theoretical | Are assumptions valid? Proofs complete? Bounds tight? | Core theorem, Key intuition |
| Position | Is argument convincing? Evidence sufficient? | Main thesis, Supporting arguments |

### Core Contribution Criteria
**NOT**:
- "We propose a new method" → Too vague
- "We achieve SOTA" → Might just be engineering

**RATHER**:
- "We identify X as the key bottleneck"
- "We show that Y is more important than Z"
- "We introduce a new framework for..."

### Cross-Paper Connection Format
```yaml
builds_on: ["2310.XXXXX", "2309.XXXXX"]  # Directly based on these works
competes_with: ["2311.XXXXX"]              # Competing methods
related: ["2312.XXXXX"]                    # Related but different direction
```

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| Only paraphrasing authors | Lack of critical thinking | Actively identify weaknesses and limitations |
| Ignoring experimental details | Focus on method, overlook experiments | Carefully analyze setup, baselines, ablation |
| Missing connections | Reading papers in isolation | Actively find related work, cite arXiv IDs |
| Vague verdict | Unwilling to judge | Take clear stance in Strengths/Weaknesses |
