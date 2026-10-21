# ContinuousStreamingASRClient

通过独立 HTTP 服务接收在线累计文本，80 ms 送音频，不保留可回写尾部，不做前缀冻结。`recognize_stream` 中 is_final 只是暂停提示；`finish_stream` 才关闭在线输入并等待尾部。`clone/reset/close` 隔离与释放会话。

F1：`recognize_stream(b"", is_final=False)` 在 micro-turn 边界只读 `GET /v1/session/{id}/result`，不提交音频；未创建会话时返回空文本，不隐式建流。读取、音频请求及 reset/close 共用线程锁，避免取消异步调用后仍在运行的 HTTP 与删除会话交错。没有独立轮询时钟。
