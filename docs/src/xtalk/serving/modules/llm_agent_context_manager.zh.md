# llm_agent_context_manager.py

## 功能、类与核心方法

将可见会话事件转换为 AgentContext。A1 在输入边界保留或生成 request_id，传递 turn、segment、prefix；已播反馈的 response_id 留在上下文，新生成请求不复用该 response_id。persistent loop 行为保持原样。

## 核心方法

_accept_event_context 从事件字段构造上下文、创建消费请求；_handle_asr_result_partial/final 处理输入，_handle_response_update/finish 转发已播事实，_handle_llm_agent_loop 产生 persistent 请求，shutdown 轻量收尾。新增 request_id 缺省时在请求边界产生，不修改来源事件。A1 保留现有多说话人 gate；新的 micro-turn 来源由 A2 接入。
