# wifiCAUC

民航大学校园网（CAUC-WIFI）门户自动登录工具（macOS）。

## 环境要求

- macOS
- Python 3.11+

## 有网时先装依赖（重要）

注销门户后通常**没有外网**，无法 `pip install`。请在**还能上网时**执行一次：

```bash
cd /path/to/wifiCAUC
./setup.sh
```

会装好 `.venv`、`playwright`、Chromium（约 100MB，缓存于本机，之后离线可用）。

## 一键启动（推荐）

```bash
cd /path/to/wifiCAUC
./start.sh
```

依赖已用 `setup.sh` 装好后，`start.sh` **不再联网下载**；若无 `config.local.yaml` 会从模板复制并提示你填账号。

```bash
./start.sh check   # 只检测，不登录
./start.sh test    # 自动化测试
```

## 安装（手动）

```bash
cd /path/to/wifiCAUC
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 配置

```bash
cp config.example.yaml config.local.yaml
# 编辑 config.local.yaml，填入学号/账号与密码
chmod 600 config.local.yaml   # 建议限制本机可读
```

`config.local.yaml` 已加入 `.gitignore`，请勿提交到 Git。

## 手动测试

```bash
source .venv/bin/activate
python -m wificauc.main once
```

`once` 会根据当前 WiFi 与外网状态输出其一：

| 输出 | 含义 |
|------|------|
| `skipped: wrong wifi` | 未连 CAUC-WIFI |
| `skipped: already online` | 已连目标 WiFi 且能上网 |
| `need_portal_login` → `login: success` | 已自动填表登录 |
| `login: failed (...)` | 登录失败（M04 将通知并暂停） |

### 与 Clash 共存（默认开启）

配置 `runtime.clash_compatible: true`（默认）时：

- **不再**用 `captive.apple.com` 判断（Clash TUN 常会误报 Success）
- **只**通过 Wi-Fi 源 IP 访问校园门户 `192.168.4.252`：有登录框 → 需登录；有「您已经成功登录」→ 已上网
- **无需**关闭 Clash；M03 浏览器也会直连门户（不走代理）

若关闭兼容模式：`clash_compatible: false`（不推荐开 Clash 时使用）。

单元测试（mock SSID / HTTP）：

```bash
./scripts/accept-m02.sh          # M02 全量验收（推荐）
python -m unittest tests.test_m02 -v
```

## 子命令（逐步实现）

| 命令 | 说明 |
|------|------|
| `once` | 检测网络并在需要时自动门户登录 |
| `run` | 常驻轮询（LaunchAgent 调用） |
| `resume` | 清除失败暂停后继续 |
| `status` | 查看上次结果与是否 paused |

详细需求见 `需求.md`，技术方案见 `plan/技术方案.md`。
