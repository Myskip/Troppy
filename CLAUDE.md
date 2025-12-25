# CLAUDE.md

本文档为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

**重要：所有问答和文档均使用中文**

## 项目概述

**Troopy** 是一个基于 Python 的 REPL（读取-求值-打印-循环）命令行工具，通过统一接口与多个 LLM（大语言模型）API 进行交互。它实现了可扩展的 Agent 框架，并支持 OpenAI 兼容的 API。

- **语言**: Python 3.9+
- **包管理器**: UV（推荐）或 pip
- **依赖项**: `prompt-toolkit` 用于交互式 CLI，`requests` 用于 API 调用
- **用途**: 为 DeepSeek、GLM-4.7 和其他 OpenAI 兼容服务提供对话式接口

## 常用命令

### 开发环境设置
```bash
# 使用 UV 安装依赖（推荐）
uv sync

# 或使用 pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 运行应用程序
```bash
# 使用 UV
uv run python src/troopy.py

# 直接使用 Python
python src/troopy.py

# 调试配置（VS Code）
# 使用 .vscode/Troopy.code-workspace 中的 "troopy调试" 启动配置
```

### 测试
当前未配置测试套件。要添加测试：
1. 创建 `tests/` 目录并添加 `test_*.py` 文件
2. 使用 `pytest`，配合 `uv run pytest` 或 `python -m pytest`

### 依赖管理
- `pyproject.toml`: 项目配置和依赖项
- `uv.lock`: 锁定的依赖版本（使用 `uv lock` 重新生成）
- `.python-version`: Python 版本要求（3.9）

## 高层架构

### 核心组件

1. **LLM 客户端抽象** (`LLMClient` 在 `src/agent.py` 中)
   - 定义 `chat()` 接口的抽象基类
   - `OpenAICompatibleClient`: 用于 OpenAI 兼容 API 的具体实现
   - 通过 threading.Event 支持请求取消

2. **Agent 系统** (`Agent` 和 `TroopyAgent` 在 `src/agent.py` 中)
   - 管理包含系统/用户/助手消息的对话历史
   - 提供消息发送、对话持久化（保存/加载 JSON）
   - `TroopyAgent` 扩展了名称、角色和 UUID 标识

3. **Agent 管理器** (`TroopyMgr` 在 `src/troopy.py` 中)
   - 用于管理多个 Agent 实例的单例模式
   - 按 ID/名称创建和跟踪 Agent
   - 维护当前活动 Agent

4. **REPL 接口** (`Troopy` 类在 `src/troopy.py` 中)
   - 具有自动补全功能的交互式命令行 (`prompt_toolkit`)
   - 实时状态显示和 ESC 键取消功能
   - 命令历史和样式化输出

### 配置
API 端点和模型在 `TroopyConfig` 类 (`src/troopy.py`) 中配置：
- 默认：DeepSeek Reasoner (`deepseek-reasoner`)，地址 `https://api.deepseek.com/v1`
- 注释的替代方案：ModelScope、GLM-4.7
- API 密钥嵌入在源代码中（建议迁移到环境变量）

### 专用 Agent
- 位于 `src/troopy_team/` 目录
- 示例：`MrYesOrNo` (`mr_yes_or_no.py`) - 仅响应 "yes"、"no" 或 "or"
- 模式：创建继承自 `TroopyAgent` 的新 Agent 类

## 开发模式

### 创建新 Agent
1. 在 `src/troopy_team/` 中创建新的 Python 文件
2. 定义继承自 `TroopyAgent` 的类
3. 通过重写方法或添加新方法实现自定义行为
4. 如果需要，使用 `TroopyMgr.instance().create_agent()` 注册

### API 客户端配置
要切换 LLM 提供商：
1. 更新 `src/troopy.py` 中的 `TroopyConfig` 类
2. 修改 `api_url`、`api_key` 和 `model` 属性
3. 确保提供商支持 OpenAI 兼容的 API 格式

### 对话持久化
- Agent 可以通过 `save_conversation()` 和 `load_conversation()` 将对话保存/加载到/从 JSON 文件
- JSON 格式与 OpenAI 聊天补全消息结构匹配

## 文件结构
```
src/
├── troopy.py          # 主 REPL 接口和配置
├── agent.py           # 核心 Agent 框架和 LLM 客户端
├── env_loader.py      # （当前为空）环境变量加载器
└── troopy_team/       # 专用 Agent 实现
    └── mr_yes_or_no.py
```

## 注意事项

- 项目全程使用中文注释和文档
- 当前不存在测试套件或 CI/CD 流水线
- API 密钥目前硬编码在 `src/troopy.py` 中 - 建议实现 `env_loader.py` 进行安全配置
- `.venv/` 目录包含在仓库中（对于 Python 项目来说不常见）
- VS Code 工作区配置包含 "troopy调试" 和 "当前文件" 的调试配置文件