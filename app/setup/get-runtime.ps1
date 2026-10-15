# ------------------------------------------------------------------
# Vocana: downloads the Windows Python runtime into app\runtime.
#
# Only for a copy of Vocana that came without it (the source code from
# GitHub). The release from amircollider.com/vocana already has it.
# The files and their SHA-256 fingerprints are in runtime.lock.json; a
# file whose fingerprint does not match is deleted, never used.
#
# Written for Windows PowerShell 5.1, which every Windows 10 and 11 has.
# ------------------------------------------------------------------
$ErrorActionPreference = 'Stop'
# The progress bar makes Invoke-WebRequest many times slower in 5.1.
$ProgressPreference = 'SilentlyContinue'
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$app = Split-Path -Parent $here
$runtime = Join-Path $app 'runtime'
$lock = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $here 'runtime.lock.json') | ConvertFrom-Json
$base = $env:TEMP
if (-not $base) { $base = [IO.Path]::GetTempPath() }
$cache = Join-Path $base ('vocana-runtime-' + $lock.python)
New-Item -ItemType Directory -Force -Path $cache | Out-Null

function Get-Sha256([string]$path) {
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
}

try {
  foreach ($f in $lock.files) {
    $path = Join-Path $cache $f.name
    $ok = $false
    if (Test-Path -LiteralPath $path) { $ok = ((Get-Sha256 $path) -eq $f.sha256) }
    if (-not $ok) {
      $mb = [math]::Round($f.size / 1MB, 1)
      Write-Host ('  downloading ' + $f.name + ' (' + $mb + ' MB)...')
      Invoke-WebRequest -Uri $f.url -OutFile $path -UseBasicParsing
      if ((Get-Sha256 $path) -ne $f.sha256) {
        Remove-Item -LiteralPath $path -Force
        throw ('The fingerprint of ' + $f.name + ' does not match. Nothing was installed.')
      }
    }
  }

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $tmp = $runtime + '.part'
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
  $site = Join-Path $tmp 'Lib\site-packages'
  New-Item -ItemType Directory -Force -Path $site | Out-Null
  foreach ($f in $lock.files) {
    $dest = $site
    if ($f.kind -eq 'python') { $dest = $tmp }
    Write-Host ('  unpacking ' + $f.name + '...')
    [System.IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $cache $f.name), $dest)
  }
  $ver = $lock.python.Split('.')
  $pth = Join-Path $tmp ('python' + $ver[0] + $ver[1] + '._pth')
  $lines = @('# Written by get-runtime.ps1. No "import site": nothing outside this folder', '# can change which modules Vocana loads.') + @($lock.pth)
  [IO.File]::WriteAllLines($pth, [string[]]$lines)
  if (Test-Path -LiteralPath $runtime) { Remove-Item -LiteralPath $runtime -Recurse -Force }
  Move-Item -LiteralPath $tmp -Destination $runtime
  Write-Host '  Vocana runtime is ready.'
  exit 0
} catch {
  Write-Host ''
  Write-Host ('  ' + $_.Exception.Message)
  exit 1
}
