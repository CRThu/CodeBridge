# CodeBridge: 面向大语言模型 (LLM) 的源代码上下文聚合工具

`CodeBridge` 是一款面向 AI 开发者设计的源代码上下文管理工具。它能将复杂的项目工程自动化转化为结构化的单一文本（Context），并支持将 AI 生成的修改方案安全地应用回本地源码，实现“代码打包 -> AI 思考 -> 自动化同步”的完整闭环。

---

## 🛠️ 核心功能

### 1. 全量打包 (Full Pack)
*   **目的**：将整个工程转化为单个 `.context.txt` 文件。
*   **特性**：自动生成 JSON 目录树，注入文件协议 Tag，智能过滤无关文件。

### 2. 增量提取 (Delta Pack)
*   **目的**：针对特定修改需求，仅提取相关文件生成 `.delta.txt`，节省 AI 的 Token 消耗。
*   **用法**：支持传入 JSON 数组或 `.json` 列表文件。

### 3. 安全执行器 (Apply / Executor)
*   **目的**：解析 AI 返回的符合协议的修改建议（New/Update/Delete），并安全应用到本地。
*   **安全性**：内置路径越界检查、忽略规则二次校验及人工交互预览确认。

### 4. 智能交互模式 (Interactive Mode)
*   **特性**：支持双击 EXE 运行。在无参数启动时，工具会提供对话式引导菜单，方便非开发人员直观操作。

### 5. 自动编码识别 (Smart Encoding)
*   **特性**：自动识别并匹配 `UTF-8`、`GB18030` (兼容 GBK/GB2312) 及 `Latin-1` 编码。无需手动配置，完美支持中文混合编码项目。

---

## 🚀 快速开始  

### 直接下载执行 (Windows)  

如果你是 Windows 用户，可以直接下载预编译的单文件版本，无需安装 Python 环境：

👉 **[下载最新 Release 版本 (v3.0)](https://github.com/CRThu/CodeBridge/releases/download/v3.0/CodeBridge.v3.0.exe)**

### 交互模式 (推荐)
直接双击 `CodeBridge.exe` 或运行 `python CodeBridge.py`（不带参数），根据屏幕提示进行：
1. 输入路径
2. 选择模式 (全量/增量/应用)

### 命令行模式
推荐使用 `uv` 运行，系统将自动配置 `pathspec` 等依赖环境：

```powershell
# 全量打包
uv run CodeBridge.py [项目路径]

# 增量打包 (命令行直接传入 JSON 数组)
uv run CodeBridge.py [项目路径] --delta "['main.py', 'utils.py']"

# 增量打包 (通过本地 JSON 文件读取列表)
uv run CodeBridge.py [项目路径] --delta ai_change_list.json

# 自动化应用 AI 的修改方案 (需要人工确认)
uv run CodeBridge.py [项目路径] --apply ai_response.txt

# 强制自动应用所有修改 (跳过确认，适合自动化工作流)
uv run CodeBridge.py [项目路径] --apply ai_response.txt --force
```

### 生产环境编译 (Windows)
双击执行 `build.bat`。该过程将调用 Nuitka 将脚本编译为 `build_out/` 目录下的独立 EXE 文件。

---

## 📋 仓库文件说明

| 文件名 | 类型 | 核心作用 |
| --- | --- | --- |
| `CodeBridge.py` | 源码 | 核心逻辑，包含逻辑过滤、目录树构建、打包及执行引擎。 |
| `config.json` | 配置 | 定义全局默认的扩展名白名单（`.py`, `.cpp`, `.js` 等）及排除目录。 |
| `.agentignore` | 配置 | 采用 Git 语法定义项目级的忽略规则（优先于全局配置）。 |
| `build.bat` | 脚本 | 自动化编译脚本。 |

---

## ⚙️ 配置说明

### 忽略优先级
1.  **最高优先级**：目标路径下的 `.agentignore` 文件。
2.  **次高优先级**：工具同级目录下的 `config.json`。
3.  **最低优先级**：脚本内硬编码的默认 `default_config`。

### 输出规则
为避免循环读取，输出文件将生成在**目标项目目录的同级位置**：
*   全量包：`[工程名].context.txt`
*   增量包：`[工程名].delta.txt`

---

## 🤖 AI 提示词 (Prompt) 最佳实践
建议将以下内容直接作为 **System Prompt** 或首句对话发送给 AI，以建立高效的工作流共识：

```text
你现在是一个辅助开发助手，我们将配合使用 CodeBridge 工具进行开发。请遵循以下两阶段工作流：

### 核心原则
由于 CodeBridge 采用【全量替换】文件的模式应用修改，请你：
- **尽可能保留**和功能修改相关的原有代码风格和相关注释。
- **使修改最小化**，仅改动必要的部分，严禁对无关代码进行重用或重构。

### 第一阶段：需求分析
当我提供项目的【全量上下文 (.context.txt)】并描述需求时：
1. 简要给出你的修改分析方案。
2. 必须：输出一个包含所有涉及修改/新建文件的相对路径的 JSON 数组，以便我为你提供更精确的增量内容。
   格式示例：["path/to/file1.py", "path/to/file2.py"]

### 第二阶段：实施修改
当我为你提供针对性的【增量文件内容 (.delta.txt)】后，请给出最终修改后的完整源码，并严格遵循以下协议格式输出，以便本机脚本自动化同步：

# 写入或更新文件
--- START OF FILE: 相对路径 ---
完整的文件源码内容...
--- END OF FILE: 相对路径 ---

# 删除文件
--- DELETE FILE: 相对路径 ---
```

---

## ⚠️ 注意事项
*   **字符编码**：本工具具备智能编码识别能力，优先尝试 `UTF-8` 和 `GB18030`。对于极端损坏的文件，将通过 `errors='ignore'` 策略跳过乱码字符，确保任务不中断。

---

## ⚖️ 许可证
Apache License 2.0

---
*本 README 及其技术建议由 Gemini 3 Flash 提供支持。*
