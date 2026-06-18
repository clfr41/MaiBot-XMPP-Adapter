# XMPP Adapter 插件代码审计报告

**日期**: 2026-06-18
**版本**: 0.1.2
**审计范围**: `R:\Users\username\Desktop\maibot-team_xmpp-adapter` 全部源码文件

---

## 一、审计发现汇总

共识别 **30+** 项问题，按严重程度分三级。

### 🔴 严重（可能导致崩溃/数据丢失）

| # | 问题 | 文件 | 描述 |
|---|------|------|------|
| 1 | asyncio task 泄漏 | `transport.py` | `_on_message`/`_on_presence_or_iq`/`_on_disconnected` 全部使用 `asyncio.create_task()` 即发即忘，无异常处理、无 task 追踪、`stop()` 时不清理。大批消息涌入时任务堆积，插件卸载后 orphan task 带过期引用继续运行 |
| 2 | 异常被统一吞没 | `plugin.py` | `handle_xmpp_gateway` 使用单条 `except Exception` 捕获所有错误，上游无法区分参数错误/网络错误/内部 bug |
| 3 | `stop()` 竞争条件 | `transport.py` | `self._connection_task = None` 在 await 取消之前就置空，重入时可能丢失引用 |
| 4 | TLS 配置逻辑混乱 | `transport.py` | `use_ssl` 不经 `hasattr` 检查直接设置；`use_ssl`（旧式 SSL/5223）和 `use_tls`（STARTTLS）概念混合 |

### 🟡 中等

| # | 问题 | 文件 | 描述 |
|---|------|------|------|
| 5 | 封装破坏 | `services/query_service.py` | `get_self_info` 直接访问 `self._action_service._transport` 私有属性 |
| 6 | payload key 覆盖 | `codecs/notice/message_codec.py` | `{"notice_type": notice_type, **payload}` 展开时 payload 的键可能覆盖 notice_type |
| 7 | 心跳监视器空壳 | `heartbeat_monitor.py` | `start/stop/touch` 全部 `pass`，但 `XmppRuntimeBuilder` 和 `XmppEventRouter` 仍正常传递回调，形成 dead code 路径 |
| 8 | `is_mentioned` 重复计算 | `codecs/inbound/message_codec.py` | `is_mentioned` 和 `is_at` 计算出完全相同的结果两次 |
| 9 | 服务层三层重复转发 | `services/` | API → QueryService → ActionService → Transport，三层方法签名几乎一样 |
| 10 | 配置中硬编码真实凭据 | `config.toml` | JID `rote.c-ri.apc@rtc.com`、密码、MUC 地址均为真实值 |
| 11 | FIELD validator 过多 | `config.py` | `XmppServerConfig` 一个类就有 8 个 `@field_validator` |

### 🟢 低优先级

| # | 问题 | 描述 |
|---|------|------|
| 12 | i18n 有日语但 README 全中文 | `_schema_i18n` 含 `ja_JP` 冗余 |
| 13 | magic string `"[empty]"` 作为 fallback | 上下游可能耦合于此值 |
| 14 | `XmppInboundTextMixin` 不是真正混用的 | 只被 `XmppInboundCodec` 继承，不如依赖注入干净 |

---

## 二、修复内容

### Segment 1: `transport.py` — 核心修复

- **新增 `_safe_create_task()` 方法**：所有后台 task 走此方法，自动异常日志（`logger.exception`）+ lifecycle 追踪（`_pending_tasks` set）+ `add_done_callback` 自动移除
- **新增 `_cancel_pending_tasks()`**：`stop()` 时 snapshot pending task 列表 → cancel → gather → 统计清理结果
- **重构 `_configure_tls()`**：
  - `use_tls=False` → 明文连接，ssl_context=None，输出安全警告
  - `use_tls=True` + 端口 5223 → 旧式 SSL（`xmpp.use_ssl = True`）
  - `use_tls=True` + 非 5223 → STARTTLS（slixmpp 默认行为）
  - CERT_NONE 配置仅在 TLS 启用时设置
- **重写 `stop()` 清理顺序**：先 disconnect → 再 cancel 连接任务 → 再 cancel 所有 pending task → 最后通知断连
- **全面 debug 日志**：消息收发、task 创建/清理、连接状态变化均有日志

### Segment 2: `plugin.py` — 异常分层

- **四级异常处理**：
  ```python
  except ValueError:          # 参数错误 → 业务异常
  except RuntimeError:        # 连接未就绪 → 运行时状态
  except asyncio.CancelledError:  # 任务取消 → 透传
  except Exception:           # 未知异常 → logger.exception + 兜底消息
  ```
- 全部生命周期方法（on_load/on_unload/on_config_update/_restart_connection_if_needed/_stop_connection）加进入和退出日志

### Segment 3: `services/` — 封装修复

- `XmppActionService` 新增 `transport` property
- `XmppQueryService.get_self_info` 改为 `self._action_service.transport`
- 两个服务类的方法都加了 debug 日志

### Segment 4: `codecs/notice/message_codec.py` — payload 覆盖

```python
# 修复前
{"notice_type": notice_type, **payload}
# 修复后
safe_payload = dict(payload)
safe_payload.pop("notice_type", None)
{"notice_type": notice_type, **safe_payload}
```

### Segment 5: `heartbeat_monitor.py` — 死代码清理

所有方法保留接口签名，但：
- `start()` 只打一行 debug 日志说明已禁用
- `stop()` 只打一行 debug 日志
- `touch()` 完全 pass

### Segment 6: `codecs/` + `filters/` + `router/` + `runtime_state/` — 日志覆盖

每个过滤决策、路由分支、状态转换均有明确日志，log line 包含关键上下文（JID、消息类型、长度、过滤模式等），DEBUG 级别不影响正常 WARNING/ERROR 输出。

---

## 三、版本更新

| 文件 | 旧值 | 新值 |
|------|------|------|
| `_manifest.json` | `"1.0.0"` | `"1.2.0"` |
| `config.toml` | `config_version = "0.1.1"` | `config_version = "0.1.2"` |
| `README.md` | 全篇 0.1.0/0.1.1 | 全篇 0.1.2，版本历史保留旧条目 |

---

## 四、遗留风险（未修复）

| 风险 | 说明 |
|------|------|
| TLS 证书跳过验证 | `CERT_NONE` 硬编码，无用户可配置选项切换为严格验证。需在 `transport._configure_tls` 增加配置项 |
| 群聊功能不完整 | MUC 加入了但消息解析、@ 检测、room roster 等功能未完善 |
| 无权限控制 | 任何能连接 XMPP 的用户都能触发机器人回复 |
| slixmpp 版本兼容 | 代码假设 slixmpp 的 API 稳定，未做版本适配 |

---

## 五、后续建议

1. **操作员白名单**：增加 `adming_jids` 配置项，限制命令触发权限
2. **TLS 严格验证选项**：支持用户配置 CA 证书路径
3. **服务层合并**：考虑将 `XmppQueryService` 和 `XmppActionService` 合并或明确职责边界
4. **多媒体支持**：XMPP 的 Jingle 或 HTTP Upload（XEP-0363）来实现图片/文件传输
5. **自动化测试**：至少为 `filters.py`、`transport._safe_create_task`、出站/入站 codec 添加单元测试
