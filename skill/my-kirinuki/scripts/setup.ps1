# 切り抜きキットの初回セットアップ（Windows）
# - 作業フォルダ %USERPROFILE%\kirinuki を作る
# - ffmpeg / Python が無ければ winget で入れる
# - 文字起こし用の Python 環境（faster-whisper）を %USERPROFILE%\kirinuki\.venv に作る
# 外部コマンドの失敗は PowerShell では止まらないので、毎回 $LASTEXITCODE で確かめる
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

function Fail($msg) { Write-Host "NG: $msg"; exit 1 }
function Refresh-Path {
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path", "User")
}

$WORK = Join-Path $HOME "kirinuki"
foreach ($d in @("素材", "文字起こし", "出力")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $WORK $d) | Out-Null
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  $needWinget = $true
} else { $needWinget = $false }

Write-Host "== ffmpeg =="
$wingetFfmpeg = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\ffmpeg.exe"
if ((Get-Command ffmpeg -ErrorAction SilentlyContinue) -or (Test-Path $wingetFfmpeg)) {
  Write-Host "OK: ffmpeg あり"
} else {
  if ($needWinget) { Fail "winget が見つかりません。Microsoft Store で「アプリ インストーラー」を入れてから、もう一度実行してください。" }
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
  if (-not ((Get-Command ffmpeg -ErrorAction SilentlyContinue) -or (Test-Path $wingetFfmpeg))) {
    Fail "ffmpeg を入れられませんでした。表示されたメッセージを確認してください。"
  }
  Write-Host "OK: ffmpeg を入れました"
}

Write-Host "== Python =="
# 使える Python（3.10〜3.12・64bit）の実体パスを探す。
# ※ Python が無くても「python」と打つと Microsoft Store が開く見せかけのコマンドがあるので、実際に動くかで確かめる
function Find-Python {
  $cands = @(
    @{ exe = "py"; a = @("-3.12") },
    @{ exe = "py"; a = @("-3.11") },
    @{ exe = "py"; a = @("-3.10") },
    @{ exe = (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"); a = @() },
    @{ exe = "python"; a = @() }
  )
  foreach ($c in $cands) {
    $exe = $c.exe; $args2 = $c.a
    if (-not ((Get-Command $exe -ErrorAction SilentlyContinue) -or (Test-Path $exe))) { continue }
    try {
      $out = & $exe @args2 -c "import sys,struct;print(sys.executable);print(sys.version_info[0]*100+sys.version_info[1]);print(struct.calcsize('P')*8)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $out.Count -ge 3) {
        $ver = [int]$out[1]; $bits = [int]$out[2]
        if ($ver -ge 310 -and $ver -le 312 -and $bits -eq 64) { return $out[0] }
      }
    } catch {}
  }
  return $null
}
$PYEXE = Find-Python
if (-not $PYEXE) {
  if ($needWinget) { Fail "winget が見つかりません。Microsoft Store で「アプリ インストーラー」を入れてから、もう一度実行してください。" }
  winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements
  Refresh-Path
  $PYEXE = Find-Python
  if (-not $PYEXE) { Fail "Python 3.12 を入れられませんでした。Codex（ChatGPTアプリ）を一度閉じて開き直してから、もう一度このスクリプトを実行してください。" }
}
Write-Host "OK: $PYEXE"

Write-Host "== 文字起こし環境（faster-whisper）=="
$VPY = Join-Path $WORK ".venv\Scripts\python.exe"
if (-not (Test-Path $VPY)) {
  & $PYEXE -m venv (Join-Path $WORK ".venv")
  if ($LASTEXITCODE -ne 0) { Fail "Python の専用環境を作れませんでした。" }
}
& $VPY -m pip install --quiet --upgrade pip
& $VPY -m pip install --quiet faster-whisper
if ($LASTEXITCODE -ne 0) { Fail "faster-whisper を入れられませんでした。ネットにつながっているか確認してください。" }
& $VPY -c "import faster_whisper; print('OK: faster-whisper', faster_whisper.__version__)"
if ($LASTEXITCODE -ne 0) {
  # DLL の読み込みエラーは Visual C++ ランタイムが無いときに起きる
  Write-Host "Visual C++ ランタイムを入れて、もう一度確かめます"
  winget install --id Microsoft.VCRedist.2015+.x64 -e --accept-source-agreements --accept-package-agreements
  & $VPY -c "import faster_whisper; print('OK: faster-whisper', faster_whisper.__version__)"
  if ($LASTEXITCODE -ne 0) { Fail "faster-whisper が読み込めません。表示されたエラーを確認してください。" }
}

$CFG = Join-Path $WORK "config.json"
if (-not (Test-Path $CFG)) {
  $json = "{`n  ""channel_name"": """",`n  ""affiliate_url"": """",`n  ""credit"": ""あべむつき【ラッキーマイン】""`n}`n"
  [System.IO.File]::WriteAllText($CFG, $json, (New-Object System.Text.UTF8Encoding($false)))
  Write-Host "config.json を作りました（チャンネル名と紹介URLは、Codexが最初に聞いて書き込みます）"
}

Write-Host ""
Write-Host "セットアップ完了：$WORK"
