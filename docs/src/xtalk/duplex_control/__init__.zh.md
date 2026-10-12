# __init__.py

## 功能、类与核心方法

协议包的公开入口。导出输入静默标记、结束标记、五种控制状态、解析结果、异常和 DuplexCorrelation。调用方从 protocol 与 timeline 模块直接使用具体实现。

## 公开符号

NO_VOICE、EOS、ControlToken、ParsedSystemMicroTurn、ProtocolParseError、DuplexCorrelation；serialize_user_micro_turn、parse_system_micro_turn、observe_system_micro_turn。

## A2/A3 更新

新增导出 WIRE_EOS、WIRE_NO_VOICE、WIRE_CONTROLS、WireMicroTurnParser 与 PrefixSnapshot。A1 论文格式 API 保留，在线模式使用官方实际 token。
