# AI 会话技能

这个仓库收集可复用的 AI 助手技能。技能规则尽量保持通用；钩子、安装和会话改名功能由各工具分别适配。

## 技能

### branch-thread-title

按 `固定前缀 | 最新任务摘要` 管理会话标题：首次优先使用 Git 分支作为固定前缀，没有分支时使用首次任务摘要；明确切换任务时才更新右侧摘要。闲聊和同一任务的追问不会主动触发改名。

- [技能说明](skills/branch-thread-title/SKILL.md)
- [各工具的支持情况](skills/branch-thread-title/references/platforms.md)
- [Codex 钩子安装说明](skills/branch-thread-title/references/install.md)

当前包含 Codex 专用的自动标题钩子和安装脚本，实际生效依赖宿主支持、信任和模型判断。其他工具目前可复用命名规则，尚未提供自动安装和自动更新适配；请以支持情况说明为准。仅加载技能不会自动安装钩子。

## 目录结构

```text
skills/
└── branch-thread-title/
    ├── SKILL.md
    ├── agents/          # Codex 专用元数据
    ├── references/      # 各宿主与安装说明
    └── scripts/         # Codex 专用安装器和钩子
```

## 使用

将 `skills/branch-thread-title` 按目标工具的技能安装方式安装或加载。启用 Codex 自动标题时，按照上面的安装说明操作；安装脚本需要 Python 3.10 或以上版本。其他工具请查看其官方技能安装文档和本仓库的支持情况。

本仓库采用 [MIT 许可证](LICENSE)。
