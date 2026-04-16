---
name: paper-notes
description: This skill should be used when the user asks to "generate paper notes", "create note cards", "extract key points from paper", or "condensed summary". Use for bullet-format notes covering Core Contribution, Method Essence, and Key Takeaways.
version: 1.0.0
---

# Paper Notes

## Input Source
**从 `{id}_deep.md` 提炼**，不是从原始论文重新分析。确保与 deep 分析一致。

## LANGUAGE RULE
**输出语言**: 中文（分析内容）+ 英文（标题/作者/术语）
- **中文**: Core Contribution, Method Essence, Key Takeaways, Strengths & Weaknesses
- **英文**: 论文标题, Meta 信息, arXiv ID, 技术术语

## Output Template

```markdown
# [Paper Title] — Notes

**Meta**: [Author 1 et al.] | [Venue] | arXiv: [XXXX.XXXXX]

**Open Source**: [OPEN] [GitHub URL] / [CLOSED] / [PENDING]

---

## Core Contribution
- **[核心创新点1]**
- **[核心创新点2]**

### Key Figures
[嵌入 3-5 张核心图片：架构图、主结果图、消融图（如适用）]

## Method Essence
- **Key Idea**: [中文一句话核心原理]
- **Why Works**: [中文解释为什么有效]

## Key Takeaways
- [可引用结论1]: [具体数据/发现]
- [可引用结论2]: [具体数据/发现]

### Key Figures
[补充嵌入关键实验结果图、消融图等]

## Strengths & Weaknesses
- **Strengths**: [优点1-2个]
- **Weaknesses**: [缺点1-2个]

## Related Work
- Builds on: [arxiv:XXXX.XXXXX]
- Competes with: [arxiv:XXXX.XXXXX]

---
*Updated: [日期]*
```

## Key Points

### Core Contribution
- Maximum 2-3 points
- Focus on what's **NEW**: new problem/new method/new data/new findings
- Don't list all the authors' work
- Use **bold** to highlight key concept names (e.g., **Occ3D 基准**, **CTF-Occ**)

### Method Essence
- **Key Idea**: Explain core principle in one sentence
- **Why Works**: Explain why it's effective, not how it's implemented

### Key Takeaways
- Each point should be a **quotable conclusion**
- Include specific numbers or clear findings
- Avoid vague statements like "performs better"

### Strengths & Weaknesses
- 1-2 points per side is enough
- **Strengths**: New paradigm/important insight/significant improvement/open source
- **Weaknesses**: Limited scenarios/insufficient experiments/computational cost/incremental

### Related Work
- **Builds on**: Previous work directly depended upon
- **Competes with**: Competing methods solving the same problem

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| Summary paraphrasing | Not extracting essence | Focus on "what's new" and "why it works" |
| Key Idea too long | Trying to explain too much | State core principle in one sentence |
| Takeaways lack data | Vague conclusions | Include specific numbers or clear findings |
| Imbalanced pros/cons | Unwilling to critique | Objectively list both sides, 1-2 points each |

## Example

```markdown
# Occ3D: A Large-Scale 3D Occupancy Prediction Benchmark for Autonomous Driving — Notes

**Meta**: Xiaoyu Tian et al. | NeurIPS 2023 | arXiv: 2304.14365

**Open Source**: [OPEN] https://github.com/Tsinghua-MARS-Lab/Occ3D (Code + Data + Benchmark)

---

## Core Contribution
- **Occ3D 基准**：首个大规模环视 3D 占用率预测数据集（nuScenes 40K 帧 + Waymo 200K 帧），解决边界框表示无法捕获不规则几何的问题
- **三阶段标注流程**：体素密集化 → 遮挡推理 → 图像引导精炼，从稀疏 LiDAR 生成密集高质量标签
- **CTF-Occ 网络**：粗到细金字塔架构 + 增量 Top-K token 选择，平衡精度与效率

## Method Essence
- **Key Idea**：从低到高分辨率逐级精炼 3D 体素特征，每级只处理 top-K 个体素
- **Why Works**：金字塔架构保留全局结构同时恢复细节；Top-K 选择避免处理所有体素的计算开销；Deformable attention 实现相关图像区域与体素的高效交互

## Key Takeaways
- **环视必要性**：前向视野数据集（SemanticKITTI）不足以支持完整 3D 理解
- **密集 vs 稀疏**：TPVFormer 因 LiDAR 监督产生稀疏输出，Occ3D 密集标签使密集预测成为可能
- **CTF-Occ vs BEVFormer**：Occ3D-nuScenes 上 +1.65 mIoU，所有语义类别均超越
- **遮挡处理关键**：LiDAR visibility mask 过滤被遮挡体素，提升标签质量

## Strengths & Weaknesses
- **Strengths**：数据集规模空前；标注流程系统严谨；完整开源（代码+数据+基准）
- **Weaknesses**：语义 mIoU 仅 ~28-30%；依赖精确传感器标定；通用物体标注粗粒度

## Related Work
- **Builds on**: BEVFormer (arXiv:2203.05625) - BEV 表示框架
- **Competes with**: TPVFormer - 稀疏 vs 密集输出

---
*Updated: 2025-01-30*
```
