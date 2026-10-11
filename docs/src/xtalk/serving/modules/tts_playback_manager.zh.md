# tts_playback_manager.py

## 功能、类与核心方法

把已确认播放进度映射为累计已播文本。A1 缓存 response 关联快照，并将其带入 ResponseUpdate、ResponseFinish、TTSResponseClosed。TTSStarted 才开启播放跟踪，提前停止仍依据客户端回执结算，已播内容不可撤回。

## 核心方法

_cache_response_update/finish 缓存文本与首次关联；_activate_response 在 TTSStarted 建立跟踪；_emit_response_update 发布累计已播前缀；_commit_playback_text 发布最终已播文本；_close_response 复制关联后清理并发布关闭事件；shutdown 取消对齐与停止超时任务。内部音频 segment 和强制对齐规则保持原有行为。
