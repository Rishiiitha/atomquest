$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
$Python = Join-Path $Root '.venv\Scripts\python.exe'
& $Python -m pip install -r requirements.txt
corepack pnpm --dir web install --node-linker=hoisted --package-import-method=copy
& $Python scripts/export_openapi.py
corepack pnpm --dir web gen:api
& $Python -m data.pipeline --quick
Write-Host 'Setup complete. Run .\scripts\demo.ps1 to start the app.'
