---
name: paper-quick
description: This skill should be used when the user asks to "generate quick scan", "quick paper review", "filter papers", or "decide whether to read". Use for one-page quick scan with One-Liner, Key Idea, and Verdict ([MUST READ]/[SKIM]/[SKIP]).
version: 1.0.0
---

# Paper Quick Scan

## Input Source
**从 `{id}_deep.md` 提炼**，不是从 notes 进一步简化。确保信息的完整性。

## LANGUAGE RULE
**输出语言**: 中文（分析内容）+ 英文（标题/作者/术语）
- **中文**: One-Line Summary, Key Idea, Method Snapshot, Verdict 理由
- **英文**: 论文标题, Meta 信息, 表格列名, 技术术语

## Output Template

```markdown
# [Paper Title] — Quick Scan

**Meta**: [Author 1 et al.] | [Venue: Year] | arXiv: [XXXX.XXXXX]

**Open Source**: [OPEN] [GitHub URL] / [CLOSED] / [PENDING]

## One-Line Summary
[中文一句话概括：方法名 + 核心创新 + 解决什么问题 + 主要结果]

## Key Idea
- [核心创新点1]
- [核心创新点2]
- [核心创新点3]

### Architecture Overview
[如有方法架构图，在此嵌入 - ![](images/xxx.jpg)]

## Method Snapshot
[方法原理简述，1-2句]

## Results Highlights
| Dataset | Metric | Score | vs SOTA |
|---------|--------|-------|---------|
| [Dataset] | [Metric] | [Score] | [+X%] |
| [Dataset] | [Metric] | [Score] | [SOTA] |

### Results Visualization
[如有结果对比图，在此嵌入]

## Verdict
[MUST READ] 必读 / [SKIM] 浏览 / [SKIP] 跳过

**理由**: [中文一句话说明评分理由]

---
```

## Verdict Criteria

### [MUST READ] Must Read
Meet at least one of:
- New problem paradigm or important insight
- Method with broad applicability
- Sufficient experiments, reliable results
- Theoretical support

### [SKIM] Skim
Meet at least one of:
- Interesting method but limited application scenarios
- Insufficient experiments but valuable idea
- Main contribution is engineering details
- Domain-specific, not general purpose

### [SKIP] Skip
Meet at least one of:
- Lacks novelty (incremental)
- Seriously insufficient experiments
- Overclaimed, insufficient evidence
- Reproducibility issues

## Key Points

### One-Line Summary
- **Format**: [Method name] + [Core innovation] + [What problem it solves] + [Main result]
- **Purpose**: Explain paper's value in one sentence
- **Example**: "ISO introduces depth-aware monocular 3D occupancy prediction for indoor scenes via D-FLoSP module, with Occ-ScanNet benchmark (40× NYUv2)"

### Key Idea
- Maximum 3 points, one line each
- Focus on **core innovation**, not all contributions
- Explain **WHAT** it is, not **HOW** it works
- Use **bold** to highlight key concept names (e.g., **Occ3D 基准**, **CTF-Occ**)

### Method Snapshot
- 1-2 sentences explaining core principle
- Don't get into implementation details
- Use analogies or simplified descriptions to aid understanding

### Results Highlights
- Present in table format for clarity
- Highlight differences vs SOTA
- Include 1-2 most important datasets

### Open Source
- **[OPEN]**: GitHub URL with content details (Code / Data / Both)
- **[CLOSED]**: No code or data available
- **[PENDING]**: Authors mention release but not yet available
- Source: Paper text, GitHub search, project website

### Verdict
- Clearly give [MUST READ]/[SKIM]/[SKIP]
- One sentence reason
- Don't be ambiguous

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| One-Line too long | Trying to include too many details | Focus on: what's new + why it matters |
| Key Idea too many | Listing all contributions | Keep only the 1-3 most essential points |
| Method too detailed | Getting lost in implementation | Explain core principle in one sentence |
| Verdict vague | Unwilling to judge | Clearly give [MUST READ]/[SKIM]/[SKIP] with reason |
| Missing comparison | Only reporting own results | Always include vs SOTA |

## Example

```markdown
# Occ3D: A Large-Scale 3D Occupancy Prediction Benchmark for Autonomous Driving — Quick Scan

**Meta**: Xiaoyu Tian et al. | NeurIPS 2023 | arXiv: 2304.14365

**Open Source**: [OPEN] https://github.com/Tsinghua-MARS-Lab/Occ3D (Code + Data + Benchmark)

## One-Line Summary
Occ3D 提出首个大规模环视 3D 占用率预测基准，通过三阶段标注流程生成密集标签，并设计 CTF-Occ 网络以粗到细金字塔架构实现高效预测。

## Key Idea
- **Occ3D 基准**：40K nuScenes + 200K Waymo 帧，首个环视密集 3D 占用率数据集
- **三阶段标注**：体素密集化（多帧聚合） → 遮挡推理（visibility mask） → 图像引导精炼（3D-2D 一致性）
- **CTF-Occ**：粗到细金字塔 + Top-K token 选择，平衡精度与效率

## Method Snapshot
使用图像 backbone 提取多视图特征，通过粗到细体素编码器（L3→L2→L1）逐级精炼 3D 特征，每级仅处理 top-K 个体素 token（deformable cross-attention 聚合图像特征），最终解码器输出体素级占用率和语义。

## Results Highlights
| Dataset | Metric | Score | vs SOTA |
|---------|--------|-------|---------|
| Occ3D-nuScenes | mIoU | ~28-30% | +1.65% vs BEVFormer |
| Occ3D-Waymo | mIoU | Consistent | SOTA |

## Verdict
[MUST READ] 必读

**理由**: 首个大规模环视 3D 占用率基准，数据集贡献显著；标注流程系统严谨可复用；完整开源促进后续研究；自动驾驶视觉感知方向必读。

---
```
