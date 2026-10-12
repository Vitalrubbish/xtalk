# protocol.py

## 功能、类与核心方法

定义 DuplexCascade 无系统附和协议。输入序列化把文本追加 EOS，空字符串编码为 no voice 加 EOS。完整输出解析严格检查五种控制 token、EOS、回答文本和额外 token，并用稳定错误码报告异常。协议观察函数使用同一关联字段发布成功或错误事件。A1 完整片段观察 API 保留；A3 使用 WireMicroTurnParser 解析在线流并由 RuntimeAdapter 执行。

## 类设计与方法契约

ControlToken 是字符串枚举；ParsedSystemMicroTurn 是不可变结果，保存 control_token、response_text 和 raw_output；ProtocolParseError 保存 code 与 raw_output。

serialize_user_micro_turn 只把空字符串编码为静默，空白字符串保持原样。parse_system_micro_turn 要求首部控制 token 与末尾 EOS；finish-speaking 后必须有非空白回答，其他四种状态只允许空白。尖括号 token 形式的额外内容被拒绝。输出文本保留原值。

错误码：missing_eos、missing_control_token、unknown_control_token、unexpected_token、missing_response_text、unexpected_response_text。observe_system_micro_turn 等待事件分发完成，成功返回解析结果，协议错误返回 None；参数类型错误直接抛 TypeError。

## A2/A3 更新

WireMicroTurnParser.feed 缓存分片 marker，只输出合法回答文本；finish 检查 EOS、空回答和服务 stop/length 原因。后续回答 micro-turn 允许普通文本；user backchannel 后也可接续写文本并保留当前回答；speaking/interruption/thinking 禁止文本，系统附和拒绝。模型预算截断仅对回答片段接受，历史保留原始截断文本。WIRE_CONTROLS 将实际 tokenizer 字符串映射到五个论文语义。
