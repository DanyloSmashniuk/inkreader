# Збирає InkReader для Windows: dist\InkReader (програма), dist\InkReader-windows.zip і, якщо встановлено
# Inno Setup 6, інсталятор dist\InkReader-setup.exe. Запускати з кореня проєкту в PowerShell.
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

# Інсталятор
python -c "from PIL import Image; Image.open('src/icon.png').convert('RGBA').save('dist/icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
$version = ((Select-String -Path buildozer.spec -Pattern '^version\s*=\s*(.+)$').Matches[0].Groups[1].Value).Trim()
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DAppVersion=$version" scripts\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup завершився з помилкою $LASTEXITCODE" }
    Write-Host "Інсталятор: $(Get-Location)\dist\InkReader-setup.exe"
} else {
    Write-Host "Inno Setup 6 не знайдено: інсталятор не створено (https://jrsoftware.org/isdl.php)"
}
Write-Host "Готово: $(Get-Location)\dist\InkReader\InkReader.exe"
