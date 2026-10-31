#requires -Version 5.1
<#
    一键发布脚本：语法自检 → 备份 → add → 读取迭代记录最新条目生成提交信息(带 [release] 标记)
                  → commit → openssl 后端 push。推送成功后，云端 Actions 自动递增 patch 并发 Release。

    用法（在项目根目录）：
      .\release.ps1                      # 自动取迭代记录最新条目作为提交信息
      .\release.ps1 "手动指定提交说明"     # 覆盖自动生成的标题
      .\release.ps1 -SkipCheck           # 跳过语法自检（不推荐）
      .\release.ps1 -NoBackup            # 跳过主程序备份
#>
[CmdletBinding()]
param(
    [string]$Message = "",
    [switch]$SkipCheck,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -LiteralPath $ROOT

$PY_EXE    = "C:\Users\Offic\AppData\Local\Programs\Python\Python310\python.exe"
$CHANGELOG = Join-Path $ROOT "docs\开发迭代记录.txt"
$INDEX     = Join-Path $ROOT "index.html"

function Fail($msg) {
    Write-Host ""
    Write-Host "✗  $msg" -ForegroundColor Red
    Write-Host ""
    exit 1
}
function Info($msg) { Write-Host $msg -ForegroundColor Cyan }

# ---------- 0. 前置检查 ----------
if (-not (Test-Path -LiteralPath $INDEX)) { Fail "未找到主程序 index.html，脚本中止。" }
if (-not (Test-Path -LiteralPath $PY_EXE)) { Fail "未找到 Python：$PY_EXE" }

$branch = git branch --show-current
if ($LASTEXITCODE -ne 0) { Fail "读取当前分支失败。" }
if ($branch.Trim() -ne "main") { Fail "当前分支为 '$($branch.Trim())'，发布脚本只允许在 main 上运行。" }

# ---------- 1. 语法自检 ----------
if (-not $SkipCheck) {
    Info "[1/6] 运行内联 JS 语法自检 (tests/_check.py) ..."
    & $PY_EXE (Join-Path "tests" "_check.py")
    if ($LASTEXITCODE -ne 0) { Fail "语法自检未通过，已中止：未提交、未推送、未发版。" }
    Write-Host ""
}

# ---------- 2. 备份当前主程序 ----------
$kv = $null
$html = [IO.File]::ReadAllText($INDEX, [Text.Encoding]::UTF8)
$m = [regex]::Match($html, "window\.__KV__\s*=\s*'([^']+)'")
if ($m.Success) { $kv = $m.Groups[1].Value }

if (-not $NoBackup -and $kv) {
    $bakDir = Join-Path $ROOT "backups"
    if (-not (Test-Path -LiteralPath $bakDir)) { New-Item -ItemType Directory -Path $bakDir | Out-Null }
    $bak = Join-Path $bakDir ("index_backup_{0}.html" -f $kv)
    if (-not (Test-Path -LiteralPath $bak)) {
        Copy-Item -LiteralPath $INDEX -Destination $bak
        Info "[2/6] 已备份主程序 -> backups/$([IO.Path]::GetFileName($bak))"
    } else {
        Info "[2/6] 备份已存在，跳过：$([IO.Path]::GetFileName($bak))"
    }
} else {
    Info "[2/6] 未取到 __KV__ 版本号，跳过备份。"
}
Write-Host ""

# ---------- 3. 暂存全部变更 ----------
Info "[3/6] git add -A ..."
git add -A
if ($LASTEXITCODE -ne 0) { Fail "git add 失败。" }

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "工作区没有需要提交的变更，已退出；未推送，也不会触发云端发版。" -ForegroundColor Yellow
    exit 0
}

# ---------- 4. 生成提交信息（迭代记录最新条目） ----------
Info "[4/6] 读取 docs/开发迭代记录.txt 最新条目 ..."
$subject = ""
$bodyLines = @()
if (Test-Path -LiteralPath $CHANGELOG) {
    $lines = [IO.File]::ReadAllLines($CHANGELOG, [Text.Encoding]::UTF8)
    $lastIdx = -1
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i] -match '^\s*第\s*\d+\s*条') { $lastIdx = $i; break }
    }
    if ($lastIdx -ge 0) {
        $subject = $lines[$lastIdx].Trim()
        for ($j = $lastIdx + 1; $j -lt $lines.Count; $j++) { $bodyLines += $lines[$j] }
    }
}
if (-not $subject) { $subject = "release: 自动发布" }
if ($Message) { $subject = $Message.Trim() }
# [release] 标记必须在首行，供云端 Actions 识别触发发版
$subject = $subject.TrimEnd() + " [release]"

$msgPath = Join-Path $ROOT ".release-commit-msg.txt"
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine($subject)
[void]$sb.AppendLine()
foreach ($b in $bodyLines) { [void]$sb.AppendLine($b) }
[IO.File]::WriteAllText($msgPath, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Info "提交标题：$subject"
Write-Host ""

# ---------- 5. 提交 ----------
Info "[5/6] git commit ..."
git commit -F $msgPath
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $msgPath -ErrorAction SilentlyContinue
    Fail "git commit 失败。"
}
Remove-Item -LiteralPath $msgPath -ErrorAction SilentlyContinue
Write-Host ""

# ---------- 6. 推送（OpenSSL 后端 + 重试） ----------
Info "[6/6] git push origin main ..."
$pushed = $false
for ($attempt = 1; $attempt -le 3; $attempt++) {
    git -c http.sslBackend=openssl push origin main
    if ($LASTEXITCODE -eq 0) { $pushed = $true; break }
    Write-Host "推送第 $attempt 次失败，5 秒后重试 ..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
if (-not $pushed) {
    Fail @"
推送失败：当前代理节点到 github.com 主域不通。本地提交已保留，不会丢失。
换一个 Clash Party 节点后，手动执行：
  git -c http.sslBackend=openssl push origin main
推送成功后云端 Actions 会自动发版。
"@
}

Write-Host ""
Write-Host "✔ 提交已推送。云端 Actions 检测到 [release] 标记后，会自动递增 patch 版本并发布 Release。" -ForegroundColor Green
Write-Host "Actions 运行状态：https://github.com/officialscholar/knowledge-cards/actions"
Write-Host "Releases 页面  ：https://github.com/officialscholar/knowledge-cards/releases"
