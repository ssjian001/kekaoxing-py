@echo off
echo ============================
echo  可测排程 - Windows 构建
echo ============================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.11
    pause
    exit /b 1
)

echo [1/3] 安装依赖...
pip install PySide6 apsw openpyxl pyinstaller

echo [2/3] 构建 EXE...
pyinstaller kekaoxing.spec --clean --noconfirm

if %errorlevel% equ 0 (
    echo.
    echo [OK] 构建成功！
    echo      输出文件: dist\可测排程.exe
    echo.
    explorer dist
) else (
    echo.
    echo [ERROR] 构建失败，请检查上方错误信息
)

pause
