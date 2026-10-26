param(
    [ValidateSet("onefile", "folder")]
    [string]$Mode = "onefile",
    [string]$Entry = "exe_entry.py",
    [string]$Name = "DrumCompanion"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$ErrorActionPreference = "Continue"
python -m pip install -e ".[build]" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
$layout = if ($Mode -eq "folder") { "--onedir" } else { "--onefile" }
# Modules that are installed alongside librosa but never used by this app.
$excludes = @(
    "pandas", "sklearn", "cryptography", "psycopg2", "PIL", "matplotlib", "IPython",
    "pytest", "tkinter", "jupyter", "notebook", "sqlalchemy", "lxml", "docutils", "setuptools"
) | ForEach-Object { "--exclude-module"; $_ }
python -m PyInstaller --noconfirm --clean $layout --noconsole `
    --name $Name `
    --icon "drum_companion\assets\icon\icon.ico" `
    --paths . `
    --add-data "drum_companion\assets;drum_companion\assets" `
    --collect-all librosa `
    --collect-all soundfile `
    --collect-all sounddevice `
    --collect-all lazy_loader `
    --collect-all numba `
    @excludes `
    $Entry
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if ($Mode -eq "folder") {
    $zip = "dist\$Name-folder.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path "dist\$Name" -DestinationPath $zip
    Write-Host "Built dist\$Name\$Name.exe and $zip"
} else {
    Write-Host "Built dist\$Name.exe"
}
