# model_client.py

## 功能、类与核心方法

DuplexModelClient 使用 aiohttp 把 micro-turn 历史发送到 /generate，历史在 user 文本与既往返回的 assistant token id 之间交替，读取逐行 NDJSON 并保留 special token。GenerationEnd 保存 stop/length 原因与实际生成的 token id，防止把官方 max_new_tokens 截断伪造为 EOS。stream 传递 HTTP、超时与模型错误；会话取消关闭连接。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与 FDB 需远端 conda 验收。

损坏 NDJSON 归为模型服务错误，运行时停止未播输出并留下错误证据。
