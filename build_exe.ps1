param(
    [ValidateSet("onefile", "folder")]
    [string]$Mode = "onefile"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$ErrorActionPreference = "Continue"
python -m pip install -e ".[build]" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
$layout = if ($Mode -eq "folder") { "--onedir" } else { "--onefile" }
python -m PyInstaller --noconfirm --clean $layout --noconsole `
    --name DrumCompanion `
    --paths . `
    --add-data "drum_companion\assets;drum_companion\assets" `
    --collect-all librosa `
    --collect-all soundfile `
    --collect-all sounddevice `
    --collect-all lazy_loader `
    --collect-all numba `
    exe_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if ($Mode -eq "folder") {
    $zip = "dist\DrumCompanion-folder.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path "dist\DrumCompanion" -DestinationPath $zip
    Write-Host "Built dist\DrumCompanion\DrumCompanion.exe and $zip"
} else {
    Write-Host "Built dist\DrumCompanion.exe"
}
