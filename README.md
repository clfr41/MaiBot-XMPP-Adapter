```markdown
# XMPP 适配器插件 (maibot-team.xmpp-adapter) v0.1.0

> **让 MaiBot 通过 XMPP 协议收发消息。**
>
> 这是一个**实验性质的原型工具**（0.1.0 早期测试版）。使用前请务必阅读本文档的全部内容，尤其是安全警告、免责声明和已知问题。

---

## 📦 安装方式

### 步骤 1：复制插件文件

将插件目录放入 MaiBot 的 `plugins/` 目录下，最终目录结构应为：

```
plugins/
└── maibot-team.xmpp-adapter/
    ├── _manifest.json
    ├── config.toml
    ├── plugin.py
    ├── README.md
    └── ... (其他运行时文件)
```

### 步骤 2：安装依赖

本插件依赖 `slixmpp` 库，需要在 MaiBot 环境中安装：

```bash
uv pip install slixmpp
```

### 步骤 3：配置并启用

编辑 `plugins/maibot-team.xmpp-adapter/config.toml`，填入 XMPP 服务器信息和机器人账号，然后启用插件。详见下文“快速开始”。

---

## ⚠️ 重要：安全警告与免责声明

### 🛡️ 安全警告

**本插件为早期测试版本（0.1.0），功能有限且可能存在大量未知 BUG。您必须了解以下全部风险：**

1. **通信安全风险**：当前测试版本**默认不启用 TLS 加密**，XMPP 连接可能以**明文**传输，包括您的账号密码、聊天内容等敏感信息。如果您在公网使用，可能遭受窃听或中间人攻击。即使启用 TLS，由于测试环境常用自签名证书，本插件默认**跳过证书验证**，同样存在中间人风险。

2. **密码明文存储**：机器人账号密码以**明文**形式保存在 `config.toml` 文件中。**绝对不要**将此文件分享、上传至代码仓库或通过不安全的渠道传输。

3. **功能极度不稳定**：
   - **图片/文件消息**：当前版本**不支持**接收或发送图片、文件、语音等非文本消息。
   - **群聊（MUC）**：群组功能**未完善**，可能无法正常加入、收发消息或管理成员。
   - **心跳/在线状态**：应用层心跳已临时禁用，在线状态检测仅依赖传输层 TCP 连接状态，可能导致误判离线或在特定网络环境下状态不同步。
   - 更多未测试或已知缺陷请见“已知问题与限制”章节。

4. **代码质量风险**：本适配器基于 napcat-adapter 架构改造而来，代码**未经充分测试**，可能存在逻辑错误、资源泄漏或崩溃风险。**强烈不建议**在生产环境或重要聊天中使用。

5. **XMPP 服务器兼容性**：仅在与 Openfire 4.x 的有限测试中验证了基本消息收发。其他 XMPP 服务器（如 Prosody、Ejabberd）未经测试，可能出现协议不兼容、认证失败、TLS 协商失败等问题。

6. **无访问控制**：当前版本未实现操作员白名单或命令权限控制。任何能连接到该机器人的 XMPP 用户都可能触发机器人回复，存在被滥用风险。

7. **无升级兼容承诺**：本插件为 0.1.0 早期测试版，配置结构、代码接口和行为可能在后续版本中发生**重大不兼容变化**，且不提供迁移工具。

### 📜 免责声明

1. **无担保（AS IS）**：本插件按“现状”（AS IS）提供，不提供任何明示或暗示的担保，包括但不限于对可用性、准确性、安全性、可靠性的担保。

2. **使用风险自负**：您使用本插件的行为完全出于您的自愿，并自行承担由此产生的**全部风险和责任**。插件开发者不对因使用本插件造成的任何直接或间接损失负责，包括但不限于数据泄露、服务中断、账号被封、财产损失等。

3. **非生产级软件**：本插件为实验原型，**禁止**用于生产环境或重要业务场景。如果您决定在生产中使用，视为您已自行进行充分评估并接受所有风险。

4. **法律合规**：您应确保使用 XMPP 协议及相关服务符合当地法律法规。插件开发者不承担因违反法律法规而导致的任何责任。

5. **知识产权**：本插件代码采用与项目主体兼容的开源许可证。XMPP 协议本身为公开标准，不受本插件限制。

6. **不可抗力**：因不可抗力（如 XMPP 服务器故障、网络中断、第三方库缺陷）导致的任何问题，开发者不承担责任。

7. **可分割性**：如本免责声明的任何条款被视为无效，不影响其余条款的效力。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install slixmpp
```

### 2. 配置账号信息

编辑 `plugins/maibot-team.xmpp-adapter/config.toml`：

```toml
[plugin]
enabled = true
config_version = "0.1.0"

[xmpp_server]
host = "127.0.0.1"          # XMPP 服务器地址
port = 5222                 # 端口，5222 为标准端口（STARTTLS），5223 为旧式 SSL
jid = "bot@example.com"     # 机器人的 JID
password = "your_password"  # 登录密码
resource = "maibot"         # 客户端资源标识
use_tls = false             # 强烈建议设为 true，但需注意证书验证问题（见下文问题）
heartbeat_interval = 0      # 已废弃，请保持为 0
reconnect_delay_sec = 5.0
action_timeout_sec = 15.0
connection_id = ""          # 可选，用于区分多个连接

[chat]
enable_chat_list_filter = true
# ... 其余聊天过滤配置保持不变
```

**关于 `use_tls`**：
- 若设为 `false`，连接将完全明文，**极度危险**，仅用于本地测试。
- 若设为 `true`，默认走 STARTTLS，但本插件**默认跳过证书验证**（测试环境自签名证书），存在中间人攻击风险。生产环境建议配置正确的证书并将 `ssl_context` 修改为严格验证。

### 3. 配置机器人账号（重要）

为了让 MaiBot 的发送服务正确识别 XMPP 机器人账号，还必须在 MaiBot 宿主配置中添加 `platforms` 条目。找到宿主配置文件（通常为 `config.yaml` 或类似），在 `bot.platforms` 列表中加入：

```yaml
bot:
  platforms:
    - "xmpp:bot@example.com"   # 请替换为你的实际 JID
```

### 4. 启用插件

重启 MaiBot 或在 WebUI 中重载插件。连接成功后，日志会显示 `XMPP 会话已建立`。

### 5. 测试收发

用另一个 XMPP 客户端向机器人发送一条文本消息，机器人应能收到并可能回复（依赖 MaiBot 的回复逻辑）。

---

## ⚠️ 已知问题与限制（0.1.0）

由于处于早期测试阶段，本插件存在**大量**已知问题和功能缺失，您很可能遇到以下情况：

| 问题 | 详情 | 影响 |
|------|------|------|
| **不支持非文本消息** | 无法接收或发送图片、文件、语音、表情等。收到非文本消息可能被丢弃或导致解析错误。 | 只能进行纯文本对话，多媒体功能完全不可用 |
| **群聊功能不完善** | 加入 MUC、收发群消息可能存在 BUG，例如无法自动加入房间、收到群消息异常、无法正确解析发送者等。 | 群聊场景不推荐使用 |
| **应用层心跳已禁用** | 心跳机制已临时禁用，仅依赖 TCP 连接状态。网络波动时可能长时间不探测，导致状态不一致。 | 机器人可能已断开但不感知，或误以为在线实则断连 |
| **TLS/SSL 证书跳过验证** | 为了兼容自签名证书，插件默认不验证 TLS 证书，存在中间人攻击风险。 | 通信内容可能在 TLS 握手时被窃听或篡改 |
| **心跳超时误报** | 早期版本心跳超时频繁误报。虽然已禁用应用层心跳，但残留逻辑可能仍会触发一条无害的 debug 日志。 | 仅日志噪音，无功能影响 |
| **未知消息类型处理不完整** | 仅处理 `chat` 和 `groupchat` 消息。`headline`、`error`、`presence` 等仅用于心跳刷新（但不影响业务）。 | 某些 XMPP 特性可能未被正确利用 |
| **资源管理** | 插件运行中的异步任务、连接清理可能不彻底，长时间运行后可能累积垃圾。 | 建议定期重启 MaiBot |
| **错误恢复** | 某些异常情况（如服务器断连后的重连）可能失败或产生异常日志。 | 必要时需手动重启插件 |

**此外，未列出的其他潜在 BUG 和稳定性问题随时可能发生。**

---

## 📁 配置文件参考

完整 `config.toml` 示例：

```toml
[plugin]
enabled = true
config_version = "0.1.0"

[xmpp_server]
host = "127.0.0.1"
port = 5222
jid = "bot@example.com"
password = "supersecret"
resource = "maibot"
use_tls = false
heartbeat_interval = 0
reconnect_delay_sec = 5.0
action_timeout_sec = 15.0
connection_id = ""

[chat]
enable_chat_list_filter = true
show_dropped_chat_list_messages = false
group_list_type = "blacklist"
group_list = []
private_list_type = "blacklist"
private_list = []
ban_user_id = []

[filters]
ignore_self_message = true
regex_filter_enabled = false
regex_filter_mode = "blacklist"
regex_filter_patterns = []
regex_filter_show_dropped = false
```

---

## 🔧 故障排查

| 问题 | 可能原因 | 解决方法 |
|------|----------|----------|
| 日志显示“连接失败: ... got an unexpected keyword argument” | slixmpp 版本 API 变动 | 本插件已修复常见 API 差异问题，如仍出现请报告 |
| 连接建立后立即断开，提示“连接未完成会话建立就断开” | TLS 协商失败或认证失败 | 检查 JID/密码是否正确；Openfire 尝试关闭 TLS 或使用 5223 端口（参考 TLS 策略） |
| 收到消息但无法发送，日志“平台 xmpp 未配置机器人账号” | 忘记在宿主配置中添加 platforms | 在宿主 bot.platforms 中添加 `xmpp:你的JID` |
| 心跳超时相关错误 | 应用层心跳已禁用，但旧配置残留 | 确保 `heartbeat_interval = 0` 且已更新到最新 plugin.py/router.py |
| Python 环境缺少 slixmpp | 未安装依赖 | `pip install slixmpp` |

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | 2026-06 | 初始原型：基本 XMPP 收发、自动重连、简易过滤、TLS/STARTTLS 支持（跳过验证）、基于 napcat-adapter 架构。大量功能未完成。 |

---

## 📜 许可证

本插件为 MaiBot 项目的插件，遵循项目主许可证（GPL v3.0 或更高版本）。

---

> **再次强调**：本插件为 0.1.0 早期测试版，**请勿用于生产环境**。使用即代表您已完全理解并接受上述所有风险与免责声明。
> 如有疑问或反馈，请通过项目渠道联系开发者。
```