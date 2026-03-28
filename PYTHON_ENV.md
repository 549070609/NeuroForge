# Python 环境说明

当前项目可用解释器：

- 项目虚拟环境：`.venv\Scripts\python.exe`
- 系统 Python：`C:\Users\bj07c\AppData\Local\Programs\Python\Python312\python.exe`

当前问题：

- `python` 命令优先命中了 `C:\Users\bj07c\AppData\Local\Microsoft\WindowsApps\python.exe`
- 这个 Windows App Execution Alias 会导致部分终端里 `python` 无法正常使用

推荐用法：

```powershell
.\scripts\Activate-ProjectPython.ps1
```

激活后当前 PowerShell 会优先使用：

- `.venv\Scripts\python.exe`
- `.venv\Scripts\pip.exe`

也可以直接调用包装脚本：

```powershell
.\scripts\python.ps1 --version
.\scripts\python.ps1 -m pytest
```

VS Code 已通过 `.vscode/settings.json` 固定到项目虚拟环境。
