# turn_detector_manager.py

## 功能、类与核心方法

将 listening 状态边界从 TTSChunkReady 改为 TTSStarted。音频生成完成不再关闭监听；交付门打开时设为 False，播放完成或停止时恢复 True。提前停止才报告 assistant_interrupted，低层音频接收保持连续。

## 核心方法

_on_audio_frame/_on_asr_partial 驱动检测；_on_assistant_text 传递累计已播事实；_on_tts_started 改 listening=False；_on_tts_playback_finished 和 _on_tts_stopped 恢复监听，提前停止同时报告打断。listening=False 表示监听用户打断而非停止音频输入。原生语义动作旁路在 A3 Duplex 模式接入时处理。
