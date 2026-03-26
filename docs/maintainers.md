# Maintainer Guide

## Design principles

- 学校规则写在适配器中，通用抓取/抽取/检索逻辑留在主框架
- 对外只暴露稳定 schema，不在下游格式中混入站点私有字段
- 检索答案必须携带证据来源，避免不可追溯总结

## Maintainer workflow

1. 在 `src/mentor_index/adapters/` 下新增学校适配器。
2. 为适配器补充至少一个列表页夹具和两个导师页夹具。
3. 运行 `mentor-index validate-adapter <adapter_name>`。
4. 补充契约测试和检索测试。
5. 更新 README 中的支持学校清单。

## Dataset policy

- 默认提交结构化导师档案、字段字典和采集元数据摘要
- 不提交原始页面 HTML/PDF 快照
- 不提交 embedding 向量值
- 全量数据库、JSONL 和 Markdown 导出优先通过 GitHub Release 附件发布
- 仓库内只保留小样本说明与可复现流程，避免 Git 历史被大文件拖重

## Release checklist

1. 跑通 `pytest`。
2. 用最新数据库执行一次 `mentor-index search faculty "<自然语言问题>" --pretty`。
3. 更新 Release 说明：抓取日期、覆盖学院、教师数、已知缺口。
4. 上传数据库、JSONL、Markdown 导出到 GitHub Release 附件。
5. 确认 README 中的下载与体验命令仍然有效。

## Review checklist

- 是否存在对私有接口、登录态或验证码页面的依赖
- 是否为“导师自述”和“招生说明”保留了来源
- 是否处理了主页缺失、外链失效、重复页面和内容未变场景
