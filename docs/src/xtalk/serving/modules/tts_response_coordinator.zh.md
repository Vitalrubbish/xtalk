# tts_response_coordinator.py

## 功能、类与核心方法

原生交付状态机按 response 保存关联快照。准备、替换、交付和抢占停止分别使用目标 response 的字段；关闭或取消时清理快照。该补丁不新增语义仲裁器，继续保持单一串行交付所有权。

## 核心方法

_handle_response_start 保存首个请求的关联快照并管理准备/抢占；_start_delivery 发出交付请求；_handle_response_closed 等待结算后释放下一响应；_handle_stop_request 清理准备项；shutdown 清理状态与缓存。_correlations 以 response_id 为键，避免用下一响应的 request_id 标记旧响应停止。
