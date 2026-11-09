# Збирає InkReader для Windows у dist\InkReader (PyInstaller). Запускати з кореня проєкту в PowerShell.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m venv .venv-build
& .\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install "kivy[base]" plyer pyphen pyinstaller pillow
pyinstaller --noconfirm --clean --name InkReader --windowed `
    --paths src --collect-submodules plyer `
    --add-data "src/icon.png;." --icon src/icon.png --exclude-module tkinter `
    src/main.py
Compress-Archive -Path dist\InkReader -DestinationPath dist\InkReader-windows.zip -Force
Write-Host "Готово: $(Get-Location)\dist\InkReader\InkReader.exe"
