# X2StreamingClient

通过独立 HTTP 服务接收 X2 在线累计文本，80 ms 送音频，不保留可回写尾部，不做前缀冻结。`recognize_stream` 中 is_final 只是暂停提示；`finish_stream` 才关闭在线输入并等待尾部。`clone/reset/close` 隔离与释放会话。
