# MentorDB

**MentorDB** 是一个用于采集高校导师公开信息、生成结构化档案并支持自然语言检索的开源项目。

它可以抓取教师主页和相关公开页面，整理出导师简介、研究方向、招生说明、联系方式和来源链接，并通过本地语义检索回答“想找做机器人的老师”或“明确写了研究生招生信息的老师”这类问题。

## 功能

- 多高校插件化适配器
- 公开页面抓取、外链跟进和增量更新
- 自然语言语义检索与带来源的问答
- 多学校、多学院、`985 / 211 / 双一流` 联合筛选
- 导师档案导出：JSON / JSONL / Markdown
- OpenClaw skill，可通过本地 CLI 调用 MentorDB
- `FastAPI + Next.js + Nginx` 一键部署到中国云服务器
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

如果你是维护者，CLI 也是本地采集 agent 的入口。

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
mentor-index search faculty "我想找明确写了研究生招生信息的控制学院老师" --school "控制科学与工程学院" --tier 985 --tier double_first_class --json
mentor-index answer "哪些老师明确写了欢迎自动化背景并强调代码能力？" --pretty
```

更多自然语言示例见 [`data/samples/demo_queries.md`](/Users/wuhong/Documents/保研资料/mentor-index/data/samples/demo_queries.md)。

## 本地采集 Agent

MentorDB 内置了一个 CLI 优先的本地采集 agent，适合维护者抓取自己想要的学校或学院：

```bash
mentor-index agent discover --school "控制科学与工程学院"
mentor-index agent preview --adapter-name zju_control_real
mentor-index agent crawl --adapter-name zju_control_real --limit 5
mentor-index agent crawl-external --limit 20
mentor-index agent report --pretty
```

如果目标学校暂时没有专用适配器，也可以先用启发式模式：

```bash
mentor-index agent discover --listing-url "https://example.edu/faculty"
mentor-index agent preview --listing-url "https://example.edu/faculty" --school "自动化学院" --university "某大学"
mentor-index agent crawl --listing-url "https://example.edu/faculty" --school "自动化学院" --university "某大学"
```

它会优先自动抓已知结构；遇到不确定页面时，诊断信息会出现在 `agent report` 中。

## WebUI

仓库内提供了一个 `FastAPI + Next.js` 的查询型 WebUI：

- Python API：`mentor-index serve-api`
- Web 前端目录：[web](/Users/wuhong/Documents/保研资料/mentor-index/web)

本地体验：

```bash
mentor-index serve-api
cd web
npm install
NEXT_PUBLIC_MENTORDB_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

首页现在支持：

- 自然语言查询
- 多个学校联合选择
- 多个学院联合选择
- `985 / 211 / 双一流` 标签筛选
- `require_admissions` / `require_lab_url` 条件筛选

筛选语义固定为：同类 OR，跨类 AND。

详情页会展示结构化段落、来源链接和已抓取的外链正文摘要。

## 一键部署

仓库内置了面向生产环境的部署目录：

- [`deploy/docker-compose.yml`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/docker-compose.yml)
- [`deploy/nginx.conf`](/Users/wuhong/Documents/保研资料/mentor-index/deploy/nginx.conf)
- [`scripts/deploy.sh`](/Users/wuhong/Documents/保研资料/mentor-index/scripts/deploy.sh)

最短路径：

```bash
cp deploy/.env.example deploy/.env
./scripts/deploy.sh
```

这会启动：

- `FastAPI` API 容器
- `Next.js` Web 容器
- `Nginx` 反向代理

如果你部署在中国大陆云服务器上，并准备通过正式域名公开访问，请先完成备案；备案完成前，更适合先用服务器 IP、测试域名或仅内网方式验证。

详细部署说明见 [`docs/deploy_cn_server.md`](/Users/wuhong/Documents/保研资料/mentor-index/docs/deploy_cn_server.md)。

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
