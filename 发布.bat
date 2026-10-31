@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === knowledge-cards 一键发布（提交 + 推送 + 云端自动发版） ===
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File ".\release.ps1" %*
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo 发布流程退出码 %RC%，请查看上方错误信息。
)
pause
