# --- Project path ---
$proj = "D:\UHD\Academic\2025 Fall\Senior Project\CodeFlowAI_v2"

# Open interactive PowerShell: cd -> activate venv -> show (venv) prompt -> stay open
powershell -NoExit -Command @"
Set-Location '$proj'
& '.\venv\Scripts\Activate.ps1'
function global:prompt {
    Write-Host '(venv)' -ForegroundColor Green -NoNewline
    ' PS ' + (Get-Location) + '> '
}
Write-Host '[OK] CodeFlowAI virtual environment activated.' -ForegroundColor Green
"@

