@echo off
chcp 65001 >nul
echo [1/2] 正在开始编译...

:: 使用 --with 强制注入依赖，确保 100% 能找到模块
call uv run --python 3.12 --with nuitka --with pathspec python -m nuitka ^
    --standalone ^
    --onefile ^
    --remove-output ^
    --python-flag=-OO ^
    --noinclude-setuptools-mode=nofollow ^
    --output-dir=build_out ^
    CodeBridge.py

if %errorlevel% equ 0 (
    echo [2/2] 编译成功！文件在 build_out 目录下。
) else (
    echo 编译失败，请检查是否安装了 C++ 编译器（如 Visual Studio 或 MinGW）。
)
pause