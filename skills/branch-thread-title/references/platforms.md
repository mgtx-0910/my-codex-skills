# 宿主适配与能力

命名策略可跨宿主复用；自动设置会话标题依赖宿主实际提供的工具或接口，不能仅因两款工具都支持 `SKILL.md` 或钩子就假设它们兼容。遇到版本或运行方式差异，应以当前宿主的工具列表与官方文档为准。

| 宿主 | 本技能包目前提供 | 自动更新状态 |
| --- | --- | --- |
| Codex | `scripts/install.py` 与 `scripts/thread_title_hook.py` | 有专用钩子；需宿主支持并信任该钩子，语义判断由模型完成。 |
| OpenCode | 通用命名规则；当前环境提供会话改名工具时可使用 | 未提供自动触发插件或安装脚本；单次加载技能不保证后续新会话自动执行。 |
| Claude Code | 通用命名规则；可向用户提供 `/rename <标题>` | 未提供自动改名适配；不要修改 Claude 的内部会话记录来伪造支持。 |
| Gemini CLI | 通用命名规则；按当前界面实际支持的方式提供建议标题 | 有提示前事件，但本包没有验证可由模型调用的会话标题修改接口，也没有提供自动集成。 |
| 其他宿主 | 通用命名规则；依当前宿主实际能力设置或建议标题 | 未适配，不能运行 Codex 专用安装脚本冒充支持。 |

## 适配新宿主的条件

先验证稳定会话 ID、首次分支和首次任务的持久化、每次提示的事件或上下文机制、读取和设置当前标题的受支持接口、识别手动更名的方法，以及安装、冲突和撤销行为。只通过目标宿主记录状态；不要读写其他产品的私有数据库来模拟接口。需要用户审核或信任时，由用户完成。

一旦能真正安装和运行该宿主的实现，再将其状态从“未提供”改为对应能力，记录受支持版本和实际测试范围。请勿只根据其他宿主的类似事件名称宣称已兼容。

## 官方资料

- Claude Code 命令：https://code.claude.com/docs/zh-CN/commands
- Claude Code Skills：https://code.claude.com/docs/en/skills
- OpenCode 工具：https://opencode.ai/docs/tools
- OpenCode Skills：https://opencode.ai/docs/skills/
- OpenCode 插件：https://opencode.ai/docs/plugins/
- Gemini CLI 钩子：https://geminicli.com/docs/hooks/reference/
- Gemini CLI Skills：https://geminicli.com/docs/cli/skills/
