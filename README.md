# wifiCAUC

民航大学校园网（**CAUC-WIFI**）门户自动登录工具，适用于 **macOS**。

连接校园 WiFi 后，工具会检测是否已能上网；若未登录门户，则用无头浏览器自动填表登录。**不会**点击门户上的「注销」。

## 环境要求

- macOS（建议 12+）
- Python 3.11+
- 已连接或可连接 **CAUC-WIFI**

## 快速开始（约 10 分钟）

### 1. 克隆并安装依赖（需外网）

注销门户后通常**没有外网**，无法 `pip install`。请在**还能上网时**执行：

```bash
git clone <你的仓库地址> wifiCAUC
cd wifiCAUC
./setup.sh
```

`setup.sh` 会创建 `.venv`、安装 `playwright` / `pyyaml`、下载 Chromium（约 100MB），并生成 `config.local.yaml` 模板。

### 2. 填写账号密码

```bash
# 若 setup 未生成，则：
cp config.example.yaml config.local.yaml
chmod 600 config.local.yaml   # 仅本用户可读，强烈建议
```

编辑 `config.local.yaml` 中的 `credentials.username` / `credentials.password`。

**安全**：`config.local.yaml` 已在 `.gitignore` 中，**切勿**提交到 Git 或发给他人。

### 3. 手动试跑一轮

```bash
./start.sh
# 或
source .venv/bin/activate
python -m wificauc.main once
```

### 4. 安装开机/登录自启（推荐）

```bash
./scripts/install-launchagent.sh
```

安装后 Agent 在后台按 `poll_interval_seconds`（默认 20 秒）轮询；连上 CAUC-WIFI 时会**立即多跑一轮**以尽快登录。

查看日志：

```bash
tail -f ~/Library/Logs/wifiCAUC/agent.log
```

卸载：

```bash
./scripts/uninstall-launchagent.sh
```

## 一键命令（`start.sh`）

```bash
./start.sh              # 检测并在需要时登录（默认 once）
./start.sh check        # 只检测，不登录
./start.sh force        # 跳过「已上网」检测，强制尝试门户
./start.sh notify-test  # 发送测试通知
./start.sh test         # 运行自动化测试
```

## CLI 子命令

| 命令 | 说明 |
|------|------|
| `once` | 检测 WiFi / 外网，需要时自动门户登录 |
| `once --force` | 强制打开门户尝试登录 |
| `run` | 常驻轮询（LaunchAgent 调用） |
| `resume` | 清除失败暂停（`state/paused`）后立即跑一轮 |
| `status` | 查看是否 paused、上次结果、当前 SSID |

`once` 典型输出：

| 输出 | 含义 |
|------|------|
| `skipped: wrong wifi` | 未连 CAUC-WIFI |
| `skipped: already online` | 已连目标 WiFi 且能上网 |
| `need_portal_login` → `login: success` | 已自动填表登录 |
| `login: skipped (paused)` | 此前失败已熔断，需 `resume` |
| `login: failed (...)` | 登录失败，已通知并写入 paused |

## 与 Clash 共存（默认开启）

配置 `runtime.clash_compatible: true`（默认）时：

- **不再**用 `captive.apple.com` 判断（Clash TUN 常会误报 Success）
- **只**通过 Wi-Fi 源 IP 访问校园门户 `192.168.4.252`：有登录框 → 需登录；有「您已经成功登录」→ 已上网
- Playwright 也会直连门户（不走代理）

若关闭：`runtime.clash_compatible: false`（开 Clash 时不推荐）。

## macOS 权限说明

- **通知**：首次失败/成功通知时，系统可能询问是否允许「终端」或 `python` 发送通知。
- **WiFi SSID**：读取当前 SSID 依赖 `networksetup` / `airport`。若 SSID 始终显示 unknown，可在 **系统设置 → 隐私与安全性 → 定位服务** 中为终端开启定位；部分机型还需 **完全磁盘访问**。
- Clash 开启且 SSID 被隐藏时，工具会尝试 **门户 IP 探测**（`wifi.fallback_portal_detect`）。

## 重要警告

- **不要**在浏览器门户页手动点击「注销」——注销后无外网，只能等连上校园 WiFi 后由本工具或 `./start.sh` 再登录。
- 自动化**仅**点击登录按钮，代码层禁止点击含「注销」的控件。

## 故障排查

| 现象 | 处理 |
|------|------|
| 登录失败后不再重试 | 查看 `python -m wificauc.main status`；修正密码后 `resume` |
| Agent 是否在跑 | `launchctl print gui/$(id -u)/com.wificauc.agent` 或看 `~/Library/Logs/wifiCAUC/agent.log` |
| 强制再登一次 | `./start.sh force` 或 `launchctl kickstart -k gui/$(id -u)/com.wificauc.agent` |
| 卸载自启 | `./scripts/uninstall-launchagent.sh` |

## 测试

```bash
./scripts/run-tests.sh       # 全部单元测试
./scripts/accept-m02.sh      # M02 验收
./scripts/accept-m05.sh      # M05 验收
```

## 项目结构（简要）

```
wifiCAUC/
├── config.example.yaml      # 配置模板
├── config.local.yaml        # 本机配置（gitignore）
├── launchd/                 # LaunchAgent plist 模板
├── scripts/
│   ├── install-launchagent.sh
│   └── uninstall-launchagent.sh
├── src/wificauc/            # 主程序
├── state/                   # paused、last_run（gitignore）
├── setup.sh / start.sh
└── plan/                    # 模块计划与技术方案
```

详细需求见 `需求.md`，技术方案见 `plan/技术方案.md`。
