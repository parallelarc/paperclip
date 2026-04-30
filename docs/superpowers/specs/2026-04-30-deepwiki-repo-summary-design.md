# DeepWiki Repo Summary — Design Spec

## 目标

扩展 paperclip 飞书机器人，支持通过 @bot 发送 GitHub 仓库链接，自动获取 DeepWiki 文档并用 LLM 生成三级分析（Deep → Notes → Quick），复用现有的论文分析管道。

## 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| DeepWiki 服务 | 托管版 deepwiki.com | 零部署，公开仓库免费 |
| 内容获取方式 | MCP Streamable HTTP（httpx 直调） | 零新依赖，JSON-RPC over POST |
| 分析管道 | 复用三步管道（换 repo 专用 prompt） | 和论文输出格式一致 |
| 飞书触发方式 | 自动识别 GitHub URL | 无需额外命令，体验一致 |

## 数据流

```
飞书 @bot 发 GitHub URL
  → feishu_ws_client.py 检测到 GitHub URL
  → deepwiki_client.py 调用 MCP 获取 wiki 内容
  → wiki 内容保存为 repos/{owner_repo}/{owner_repo}.md
  → analyzer_sdk.py 三步管道（repo 专用 prompt）
  → Quick 结果推送飞书卡片
```

URL 解析优先级：arXiv → CVF → HF → GitHub。

## 模块改动

### 新增文件

#### 1. `src/deepwiki_client.py`

DeepWiki MCP 客户端，通过 httpx 调用 `https://mcp.deepwiki.com/mcp`。

```python
def fetch_repo_wiki(repo_url: str) -> tuple[str, str]:
    """
    从 DeepWiki 获取仓库文档。

    Returns: (repo_id, wiki_markdown)
    """
```

内部流程：
1. 解析 GitHub URL，提取 `owner/repo`
2. 发送 JSON-RPC `initialize` 请求
3. 调用 `read_wiki_structure` 获取主题列表
4. 遍历调用 `read_wiki_contents` 获取每个主题的内容
5. 合并为单个 Markdown，截断到 ~60K 字符
6. 保存到 `repos/{owner_repo}/{owner_repo}.md`

MCP 调用格式（Streamable HTTP）：
- POST `https://mcp.deepwiki.com/mcp`
- Content-Type: `application/json`
- Body: `{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "...", "arguments": {...}}, "id": N}`
- 需先发 `initialize` 请求建立会话

MCP 工具参数（实现时需通过 `tools/list` 验证）：
- `read_wiki_structure`: 预期参数 `repo_url` 或 `owner` + `repo`
- `read_wiki_contents`: 预期参数同上 + 可能的页码/路径参数

重试：3 次，指数退避 30s * attempt，仅对网络错误和 5xx 重试。

#### 2. `.claude/skills/paper-reader/references/repo-deep.md`

Repo 深度分析 prompt 模板。聚焦：
- 项目定位与核心价值
- 架构设计与模块划分
- 核心模块详解（关键数据结构、算法、流程）
- 技术选型与依赖关系
- 代码质量与可维护性评估
- 与同类项目的对比

输入：DeepWiki 的 wiki 内容（Markdown 格式）。

#### 3. `.claude/skills/paper-reader/references/repo-notes.md`

Repo 笔记 prompt 模板。聚焦：
- 核心贡献（一句话）
- 架构精髓（为什么这样设计）
- 关键要点（3-5 点）
- 优势与不足
- 适用场景

#### 4. `.claude/skills/paper-reader/references/repo-quick.md`

Repo 速览 prompt 模板。聚焦：
- 一句话总结
- 核心功能（最多 3 点）
- 技术栈
- Verdict：[MUST READ] / [SKIM] / [SKIP]
- 保持和论文一样的 Verdict 格式，飞书卡片颜色编码一致（绿/蓝/灰）

### 修改文件

#### 5. `src/arxiv.py`

新增 GitHub URL 解析：

```python
GITHUB_PATTERN = re.compile(
    r'https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?(?:/.*)?$'
)

def extract_github_repo_id(url: str) -> str | None:
    """从 GitHub URL 提取 owner_repo 格式的 ID。"""

def parse_github_url(text: str) -> str | None:
    """从文本中提取 GitHub 仓库 URL。"""
```

`parse_arxiv_url()` 不改动。新增独立的 `parse_github_url()`，在飞书客户端中 arxiv 解析失败后调用。

#### 6. `src/analyzer_sdk.py`

新增 repo 模式支持：

```python
_REPO_TEMPLATE_DEEP = _SKILL_DIR / "references" / "repo-deep.md"
_REPO_TEMPLATE_NOTES = _SKILL_DIR / "references" / "repo-notes.md"
_REPO_TEMPLATE_QUICK = _SKILL_DIR / "references" / "repo-quick.md"

_REPO_SYSTEM_PROMPT = (
    "你是一位资深软件架构分析专家。"
    "严格按照给定的输出模板格式分析开源项目，用中文输出分析内容，"
    "保留英文术语、项目名和库名。"
    "不要包裹在 ```markdown ... ``` 中，直接输出 markdown 内容。"
)

def analyze_repo(
    repo_url: str,
    repos_dir: str | Path | None = None,
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> dict:
    """
    从 GitHub URL 获取 DeepWiki 文档并执行三步分析。

    Returns: 和 analyze() 相同格式的 dict。
    """
```

`analyze()` 函数不改动。`analyze_repo()` 是独立函数，内部调用 `deepwiki_client.fetch_repo_wiki()` 获取内容，然后复用 `_call_with_retry()` 和三步管道逻辑，但加载 repo 专用 prompt 和 `_REPO_SYSTEM_PROMPT`。

输出目录为 `repos/{repo_id}/`（独立于 `papers/` 目录），结构和论文一致。

#### 7. `src/feishu_ws_client.py`

修改消息处理逻辑：

```python
# 现有：尝试解析论文 URL
url = parse_arxiv_url(text)

# 新增：论文 URL 不存在时，尝试 GitHub URL
if not url:
    github_url = parse_github_url(text)
    if github_url:
        # 调用 analyze_repo 而非 analyze_from_url
        ...
```

#### 8. `src/config.py`

新增配置项：

```python
deepwiki_mcp_url: str = "https://mcp.deepwiki.com/mcp"
```

通过 `DEEPWIKI_MCP_URL` 环境变量覆盖。

### 不改的文件

- `fetch_paper.py`、`tex_fetcher.py`、`tex_converter.py` — 仅处理论文
- `webhook.py` — 推送逻辑不变
- `hf_daily_papers.py` — 仅处理 HF 论文
- `huggingface.py` — 仅处理 HF API
- `state.py` — 可能后续扩展，本期不改动

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 仓库未被 DeepWiki 索引 | 回复"该仓库尚未被 DeepWiki 索引，请先访问 deepwiki.com 生成" |
| MCP 调用超时/网络错误 | 重试 3 次（30s * attempt 退避），失败后回复错误卡片 |
| Wiki 内容过长 | 截断到 ~60K 字符，保留前面部分 |
| GitHub URL 带 `.git` 后缀 | 剥离 |
| GitHub URL 带子路径 | 只取 `owner/repo` 部分 |
| 非 GitHub 仓库 URL | 第一期不支持，回复提示 |
| 论文 URL 和 GitHub URL 同时出现 | 优先论文（现有行为不变） |
| 非法 URL | 回复"未找到有效的论文或 GitHub 仓库链接" |
| 分析缓存已存在 | 跳过分析，直接返回缓存的 quick.md |

## 范围边界

### 本期包含
- GitHub 公开仓库分析（通过 DeepWiki MCP）
- 飞书 @bot 触发
- 三步分析管道（Deep → Notes → Quick）
- 缓存机制
- 错误处理与用户反馈

### 本期不包含
- GitLab / Bitbucket 仓库支持
- 私有仓库支持
- CLI 命令行触发（仅飞书 @bot）
- 自部署 DeepWiki-Open 切换
- HF 定时推送中的仓库分析
