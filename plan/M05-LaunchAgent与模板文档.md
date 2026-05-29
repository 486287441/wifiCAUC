# M05 — LaunchAgent 与模板文档

**技术依据**：见 `plan/技术方案.md` §3.2、§3.3、`share_template`。

**依赖**：M01–M04 完成。

## 目标

开机/登录后自动常驻轮询；README 让同学能独立安装；提供安装/卸载脚本。

## 实现要点

### `launchd/com.wificauc.agent.plist.template`

- `Label`: `com.wificauc.agent`
- `ProgramArguments`: `{{VENV_PYTHON}}`, `-m`, `wificauc.main`, `run`
- `RunAtLoad`: true
- `KeepAlive`: true（进程异常退出时重启）
- `StandardOutPath` / `StandardErrorPath` → `~/Library/Logs/wifiCAUC/`

### `scripts/install-launchagent.sh`

1. 检测 `.venv` 与 `config.local.yaml` 存在。
2. `sed` 替换 plist 中 python 绝对路径。
3. `launchctl load -w ~/Library/LaunchAgents/com.wificauc.agent.plist`。
4. 提示查看日志路径。

### `scripts/uninstall-launchagent.sh`

- `launchctl bootout` + 删除 plist。

### `main run`

- 循环：`poll_interval_seconds`（默认 20）。
- SSID 从非目标 → 目标时**立即**多跑一轮（实现 `last_ssid` 变量）。
- 整合 M02–M04 全流程。

### `README.md`（模板文档）

- 适用：民航大学 CAUC-WIFI + macOS。
- 安装步骤、权限说明、`playwright install`、配置示例。
- **安全**：`chmod 600 config.local.yaml`；勿提交密码。
- **警告**：不要在校门户页点注销。
- 故障：`status`、`resume`、查看日志。

## 验收标准

- [ ] 执行 `install-launchagent.sh` 后重启或 `launchctl kickstart`，Agent 在后台运行。
- [ ] 断开再连 CAUC-WIFI（或模拟 SSID 变化），能在 1 分钟内自动尝试登录（已上网则跳过）。
- [ ] `uninstall-launchagent.sh` 后不再自动运行。
- [ ] 新同学按 README 从 clone 到装好 Agent ≤15 分钟（人工走查一次）。
- [ ] 满足 PRD §7 全部成功标准。

## 操作步骤

### 第 1 步

完成 plist 模板与 install/uninstall 脚本。

### 第 2 步

完善 `main run` 与 README；本机端到端验收后归档。

用户回复 **通过** 即 **项目 plan 阶段完成**，进入日常维护或可选增强（钥匙串、菜单栏 App 等，另开需求）。
