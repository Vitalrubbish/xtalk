# protocol.py

## 功能、类与核心方法

定义 DuplexCascade 无系统附和协议。输入序列化把文本追加 EOS，空字符串编码为 no voice 加 EOS。完整输出解析严格检查五种控制 token、EOS、回答文本和额外 token，并用稳定错误码报告异常。协议观察函数使用同一关联字段发布成功或错误事件。A1 完整片段观察 API 保留；A3 使用 WireMicroTurnParser 解析在线流并由 RuntimeAdapter 执行。

## 类设计与方法契约

ControlToken 是字符串枚举；ParsedSystemMicroTurn 是不可变结果，保存 control_token、response_text 和 raw_output；ProtocolParseError 保存 code 与 raw_output。

serialize_user_micro_turn 只把空字符串编码为静默，空白字符串保持原样。parse_system_micro_turn 要求首部控制 token 与末尾 EOS；finish-speaking 后必须有非空白回答，其他四种状态只允许空白。尖括号 token 形式的额外内容被拒绝。输出文本保留原值。

错误码：missing_eos、missing_control_token、unknown_control_token、unexpected_token、missing_response_text、unexpected_response_text。observe_system_micro_turn 等待事件分发完成，成功返回解析结果，协议错误返回 None；参数类型错误直接抛 TypeError。

## A2/A3 更新

WireMicroTurnParser.feed 缓存分片 marker，返回按到达顺序排列的 WireControl 与 WireText 事件列表。WireControl 同时保存实际 spelling 与对应论文语义；WireText 保存回答文本并携带其前面的控制上下文。每个实际 marker 都按到达顺序执行，相邻、重复或乱序的控制 token 均保持有效。未知尖括号 spelling 作为普通语音文本处理，未结束片段同样保留为文本。WIRE_EOS 结束当前 micro-turn；WIRE_NO_VOICE 与 WIRE_IM_START 不进入语音。finish 记录 stop 或 length 终止原因。WIRE_CONTROLS 将实际 tokenizer 字符串映射到五个论文语义；A1 完整输出解析器保留严格错误码，作为论文格式校验的参照。
