@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set proxyfile=proxies.txt
set outputfile=Aproxies.txt

if not exist "%proxyfile%" (
    echo 错误：找不到 %proxyfile%，请将代理列表保存为每行 ip:port 的文本文件。
    pause
    exit /b 1
)

:: 文件不存在则创建空文件（避免后续写入失败）
if not exist "%outputfile%" type nul > "%outputfile%"

set testurl=http://www.baidu.com
set timeout=5

set total=0
set available=0
set unavailable=0

echo ========================================
echo 开始测试代理（测试URL: %testurl%）
echo 超时时间: %timeout% 秒
echo 可用代理将追加保存至: %outputfile%
echo ========================================

:: 检查是否有 curl（Windows 10+ 自带）
where curl >nul 2>nul
if %errorlevel% equ 0 (
    echo 使用 curl 测试...
    echo.
    for /f "usebackq tokens=1,2 delims=:" %%a in ("%proxyfile%") do (
        set /a total+=1
        set ip=%%a
        set port=%%b
        set /p =[!total!] 测试 !ip!:!port! ...<nul
        set code=
        for /f "delims=" %%c in ('curl -x http://!ip!:!port! -s -o nul -w "%%{http_code}" %testurl% --connect-timeout %timeout% --max-time %timeout% 2^>nul') do set code=%%c
        if "!code!"=="200" (
            echo 可用
            echo !ip!:!port!>> "%outputfile%"
            set /a available+=1
        ) else if "!code!"=="" (
            echo 不可用（无响应）
            set /a unavailable+=1
        ) else (
            echo 返回码 !code!（未保存）
            set /a unavailable+=1
        )
    )
) else (
    echo 未找到 curl，改用 PowerShell 测试...
    echo.
    for /f "usebackq tokens=1,2 delims=:" %%a in ("%proxyfile%") do (
        set /a total+=1
        set ip=%%a
        set port=%%b
        set /p =[!total!] 测试 !ip!:!port! ...<nul
        powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%testurl%' -Proxy 'http://!ip!:!port!' -TimeoutSec %timeout% -UseBasicParsing; if ($r.StatusCode -eq 200) { write-host '可用' -ForegroundColor Green; exit 0 } else { write-host ('返回码 '+$r.StatusCode) -ForegroundColor Yellow; exit 1 } } catch { write-host '不可用' -ForegroundColor Red; exit 2 }" >nul 2>&1
        if !errorlevel! equ 0 (
            echo !ip!:!port!>> "%outputfile%"
            set /a available+=1
        ) else (
            set /a unavailable+=1
        )
    )
)

echo ========================================
echo 测试完成！
echo 总代理数: %total%
echo 可用代理: %available%
echo 不可用代理: %unavailable%
echo 可用列表已追加至: %outputfile%
echo ========================================
pause