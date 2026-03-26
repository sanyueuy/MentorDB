# MentorDB

**MentorDB** 是一个用于采集高校导师公开信息、生成结构化档案并支持自然语言检索的开源项目。

它可以抓取教师主页和相关公开页面，整理出导师简介、研究方向、招生说明、联系方式和来源链接，并通过本地语义检索回答“想找做机器人的老师”或“明确写了研究生招生信息的老师”这类问题。

## 功能

- 多高校插件化适配器
- 公开页面抓取、外链跟进和增量更新
- 自然语言语义检索与带来源的问答
- 导师档案导出：JSON / JSONL / Markdown
- OpenClaw skill，可通过本地 CLI 调用 MentorDB
- 面向开源维护的稳定 schema、示例适配器和测试夹具

## 项目结构

```text
mentor-index/
  src/mentor_index/
    adapters/    # 学校适配器插件
    cli/         # Typer CLI
    core/        # 领域模型与配置
    crawl/       # 抓取流程与链接遍历
    db/          # 数据库模型、schema、仓储
    export/      # 档案与数据集导出
    extract/     # 页面抽取与归一化
    index/       # 切块与 embedding
    providers/   # 本地 embedding / 云端 LLM provider
    retrieve/    # 搜索与问答
  data/contracts/
  tests/
```

## 快速开始

### 1. 安装 CLI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

默认就是本地 `sentence-transformers` 语义向量模型，Apple Silicon 会优先使用 `MPS`。

### 2. 配置

复制环境变量模板：

```bash
cp .env.example .env
```

关键配置：

- `MENTOR_INDEX_DATABASE_URL`：默认 Postgres 连接串
- `MENTOR_INDEX_EMBEDDING_BACKEND`：默认 `sentence-transformers`；测试可用 `stub`
- `MENTOR_INDEX_EMBEDDING_MODEL`：本地 embedding 模型名，默认 `BAAI/bge-small-zh-v1.5`
- `MENTOR_INDEX_EMBEDDING_DEVICE`：`auto` / `mps` / `cpu`
- `MENTOR_INDEX_LLM_BASE_URL`：OpenAI 兼容 API 根地址
- `MENTOR_INDEX_LLM_API_KEY`：云端 LLM 密钥
- `MENTOR_INDEX_LLM_MODEL`：云端模型名

### 3. 初始化数据库

```bash
mentor-index init-db
```

### 4. 验证示例适配器

```bash
mentor-index validate-adapter zju_control
```

### 5. 抓取与建索引

```bash
mentor-index crawl school zju_control
mentor-index index embeddings
mentor-index build profiles --output-dir out/profiles
```

### 6. 搜索

```bash
mentor-index search faculty "偏工程落地、愿意带自动化背景学生的老师" --pretty
mentor-index search faculty "我想找明确写了研究生招生信息的控制学院老师" --json
mentor-index answer "哪些老师明确写了欢迎自动化背景并强调代码能力？" --pretty
```

更多自然语言示例见 [`data/samples/demo_queries.md`](/Users/wuhong/Documents/保研资料/mentor-index/data/samples/demo_queries.md)。

## 数据与发布

- 代码仓库默认只提交源码、schema、文档、测试夹具和小样本说明
- 全量数据库、JSONL、Markdown 导出通过 GitHub Release 附件发布
- 仓库默认不提交原始网页快照和向量值

推荐体验流程：

1. 安装 `mentor-index`
2. 从 Release 下载最新数据库
3. 设置 `MENTOR_INDEX_DATABASE_URL`
4. 直接运行自然语言检索

例如：

```bash
export MENTOR_INDEX_DATABASE_URL='sqlite+pysqlite:///./zju_three_schools_deep.db'
mentor-index search faculty "我想找做机器人的老师" --pretty
```

## OpenClaw Skill

仓库内提供了一个可复用的 OpenClaw skill：

- [`skills/mentordb/SKILL.md`](/Users/wuhong/Documents/保研资料/mentor-index/skills/mentordb/SKILL.md)

它只依赖本地 CLI 和数据库：

- binary: `mentor-index`
- env: `MENTOR_INDEX_DATABASE_URL`

适合让 OpenClaw 先调用本地检索，再基于证据片段给出自然语言总结。

## 默认实现约束

- 仅抓取公开可访问内容，不登录、不绕过限制
- 外链默认允许跨域，但受最大深度、最大页面数和 URL 去重约束
- 仓库默认发布结构化数据与档案，不提交原始网页快照和向量值

## 开源维护

- 适配器必须通过契约测试后再合并
- 标准化输出需符合 [`data/contracts/faculty_profile.schema.json`](/Users/wuhong/Documents/保研资料/mentor-index/data/contracts/faculty_profile.schema.json)
- 维护说明见 [`docs/maintainers.md`](/Users/wuhong/Documents/保研资料/mentor-index/docs/maintainers.md)
