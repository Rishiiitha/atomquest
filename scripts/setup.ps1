$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
$Python = Join-Path $Root '.venv\Scripts\python.exe'
& $Python -m pip install -r requirements.txt
Push-Location (Join-Path $Root 'web')
try {
    corepack pnpm install --node-linker=hoisted --package-import-method=copy
    if ($LASTEXITCODE -ne 0) { throw 'pnpm install failed. Check Corepack and the pinned pnpm version.' }
}
finally {
    Pop-Location
}
& $Python scripts/export_openapi.py
Push-Location (Join-Path $Root 'web')
try {
    corepack pnpm gen:api
    if ($LASTEXITCODE -ne 0) { throw 'OpenAPI TypeScript generation failed.' }
}
finally {
    Pop-Location
}
& $Python -m data.pipeline --quick
Write-Host 'Setup complete. Run .\scripts\demo.ps1 to start the app.'
