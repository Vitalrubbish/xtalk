# model_client.py

## 功能与类

DuplexModelClient通过aiohttp提交完整micro-turn历史并读取NDJSON，保留special token和实际生成ID。GenerationEnd保存stop/length原因、token_ids及独立的服务耗时/缓存metrics，避免把长度截断伪造为EOS。

## 核心方法

stream提交history、max_new_tokens、session_id、request_id及use_cache，发布带单调时钟的请求诊断；按text增量和GenerationEnd输出，传播HTTP、协议和模型错误。构造器支持显式会话身份与缓存诊断开关；线上由运行适配器默认开启KV复用。

release在推理停止后请求DELETE /cache/{session_id}，超时或传输错误交服务TTL回收。Python3.10使用asyncio.TimeoutError捕获异步超时，保持会话关闭完成。取消会关闭连接；缓存按会话隔离，历史仍完整提交。
