$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
py -m pip install --user -r requirements.txt
py -m mailscan2026.app
