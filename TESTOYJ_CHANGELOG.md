# testoyj 更新日志

本文件只记录 `zHydeol/OnmyojiAutoScript` 的 `testoyj` 分支改动，独立于上游 README 和发布说明。

## 2026-08-26

### 周计划后端

- 新增按配置保存的周计划，可为周一至周日分别编排任务和运行时间。
- 新增周计划查询、保存和“立即同步今日计划”接口，供 OASX 周计划页面使用。
- 返回 OAS 服务端当前时间、本周周一、计划日期、今日同步时间，以及计划内和计划外任务状态。
- 支持“补跑今日已过计划”：开启后，当天已经错过的计划会进入主调度器；关闭后会跳过，不覆盖这些任务当前的调度时间。
- 周计划启用后，每个自然日只自动同步一次。OAS 持续运行时会在次日 00:00 唤醒调度器；OAS 未运行时，会在下次启动后同步当天计划。
- 每日同步采用合并逻辑：只启用并更新时间表中当天安排的任务，不清空主调度器，也不修改当天未安排的任务。
- 同步完成后，任务成功间隔、失败重试和其他重新调度仍由 OAS 主调度器负责，周计划不会在当天反复覆盖。
- 周计划数据保存在 `config/weekly_schedule/`，该目录中的个人计划文件不会提交到 Git。

### 弈棋自动化

- 新增弈棋任务的自动执行流程。
- 补充 GameUi 页面导航，并放宽相关页面切换处理，提高弈棋流程兼容性。

### 兼容说明

- 周计划界面需要配套使用 `zHydeol/OASX` 的 `testoyj` 分支。
- 上游 OASX `v0.3.12` 不包含周计划编辑界面。
- `config/*.json` 中的账号配置属于本机数据，已由 `.gitignore` 排除，不会随分支或构建产物发布。

## 分支基线

- 上游仓库：<https://github.com/AzurTian/OnmyojiAutoScript>
- 分支仓库：<https://github.com/zHydeol/OnmyojiAutoScript/tree/testoyj>
- 本轮改动基于上游 `mine` 分支提交 `b9fe715f`。
- 配套 OASX 更新日志：<https://github.com/zHydeol/OASX/blob/testoyj/TESTOYJ_CHANGELOG.md>
