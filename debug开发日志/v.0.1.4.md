# Changelog

## 0.1.4 (2026-06-19)

### 安全

- **`slixmpp` 日志级别改为配置驱动**：新增 `plugin.slixmpp_log_level` 配置项（可选 `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`，默认 `INFO`），替代此前 `on_load` 中无条件设 `DEBUG` 的硬编码行为，生产环境不再输出完整 XMPP stanza 内容。
- **密码脱敏**：`XmppTransportClient` 在 `configure()` 时从 `XmppServerConfig` 复制密码到传输层私有字段 `_password`，`stop()` 时主动清零。配置模型自身不再长期持有密码敏感副本。
- **配置版本同步**：`SUPPORTED_CONFIG_VERSION`、`_manifest.json`、`config.toml` 示例统一为 `"0.1.4"`。

### 重构

- **服务层合并**：移除 `XmppQueryService`，其 `send_message`/`send_presence`/`join_muc`/`get_self_info` 方法直接并入 `XmppActionService`。消除冗余抽象层。
- **派发去重**：`plugin.py:_dispatch_outbound_action` 改为委托给 `self._action_service`，配合 `apis/support.py:_call_xmpp_action` 消除两套并行 dispatch 逻辑。
- **过滤管道抽取**：新增 `XmppInboundFilterPipeline` 类（`runtime/filter_pipeline.py`），将 `handle_inbound_message` 中的 from_jid 验证 → body 验证 → JID 解析 → 自身消息过滤 → 聊天名单过滤 → 正则过滤串联为显式 5 步管道，便于单测和新增规则。
- **API 层简化**：`XmppApiSupportMixin` 移除 `_require_query_service()` 方法，所有 API 端点统一使用 `_require_action_service()`。

### 移除

- **`heartbeat_monitor.py` 完全移除**：所有方法均为空实现（死代码），连带清理 `XmppRuntimeBundle`、`XmppRuntimeBuilder`、`XmppEventRouter` 中所有关联调用点。

### 清理

- **`types.py`**：移除未使用的 `XmppMutablePayload`、`XmppOptionalIdInput`、`XmppPayloadList`、`XmppIncomingSegments` 类型别名及相关导入。
- **`codecs/inbound/message_codec.py`**：移除未使用的 `query_service` 构造参数（`self._query_service` 从未被引用）。
- **`apis/support.py`**：修复重复 docstring 问题。
- **未使用 import 清理**：`config.py`（`Tuple`）、`inbound/message_codec.py`（`Mapping`/`Optional`/`Tuple`）、`runtime/router.py`（`Mapping`/`asyncio`）、`runtime/filter_pipeline.py`（`Mapping`）、`apis/support.py`（`List`）、`runtime/builder.py`（`Awaitable`）。

---

## 0.1.3 (2026-06)

- 修复：presence/IQ stanza 被错误送入消息处理管道导致空消息污染
- 修复：router 新增 body 空值守卫兜底过滤
- 新增：`tls_verify` 配置项，允许生产环境启用证书验证
- 新增：manifest 中 slixmpp 依赖和 capabilities 声明

## 0.1.2 (2026-06)

- 修复：asyncio task 泄漏（统一追踪+清理）
- 修复：异常处理分级（ValueError/RuntimeError/CancelledError）
- 修复：通知编解码 payload key 覆盖
- 修复：TLS 默认启用+逻辑重构
- 修复：心跳死代码清理
- 修复：服务层封装性修复
- 其他：全面添加 debug 日志

## 0.1.1 (2026-06)

- 部分修复了群组问题
- 更新了 config，支持通过配置加入群组

## 0.1.0 (2026-06)

- 初始原型：基本 XMPP 收发、自动重连、简易过滤、TLS/STARTTLS 支持（跳过验证）
- 基于 napcat-adapter 架构
