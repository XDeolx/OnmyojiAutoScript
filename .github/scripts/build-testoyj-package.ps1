[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryUrl,

    [Parameter(Mandatory = $true)]
    [string]$Branch,

    [Parameter(Mandatory = $true)]
    [string]$BaseArchive,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$ExpectedCommit = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,

        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code: $LASTEXITCODE)"
    }
}

function Copy-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    & robocopy.exe $Source $Destination /E /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy $Source (robocopy exit code: $LASTEXITCODE)"
    }
}

$archivePath = (Resolve-Path -LiteralPath $BaseArchive).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'oas-testoyj-package-' + [guid]::NewGuid().ToString('N')
)
$extractRoot = Join-Path $workRoot 'base'
$packageName = 'OnmyojiAutoScript-testoyj'
$packageRoot = Join-Path $workRoot $packageName

New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

try {
    Invoke-NativeCommand -FailureMessage 'Failed to extract the official easy-install package' -Command {
        & 7z.exe x $archivePath "-o$extractRoot" -y
    }

    $toolkitDirectory = Get-ChildItem -LiteralPath $extractRoot -Directory -Recurse |
        Where-Object { $_.Name -eq 'toolkit' } |
        Select-Object -First 1
    if ($null -eq $toolkitDirectory) {
        throw 'The official easy-install package does not contain a toolkit directory'
    }
    $baseRoot = $toolkitDirectory.Parent.FullName

    Invoke-NativeCommand -FailureMessage 'Failed to create the shallow testoyj checkout' -Command {
        & git clone --depth 1 --branch $Branch --single-branch $RepositoryUrl $packageRoot
    }

    $packageCommit = (& git -C $packageRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $packageCommit) {
        throw 'Failed to read the packaged source commit'
    }
    if ($ExpectedCommit -and $packageCommit -ne $ExpectedCommit) {
        throw "Branch head $packageCommit does not match release commit $ExpectedCommit"
    }

    Copy-Directory -Source $toolkitDirectory.FullName -Destination (Join-Path $packageRoot 'toolkit')

    foreach ($relativePath in @('oas.exe', 'console.bat', 'oas-backend.bat')) {
        $sourcePath = Join-Path $baseRoot $relativePath
        if (Test-Path -LiteralPath $sourcePath -PathType Leaf) {
            Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $packageRoot $relativePath) -Force
        }
    }
    foreach ($relativePath in @(
        'deploy\launcher\oas-backend.bat',
        'deploy\launcher\oas-server.bat'
    )) {
        $sourcePath = Join-Path $baseRoot $relativePath
        if (Test-Path -LiteralPath $sourcePath -PathType Leaf) {
            $destinationPath = Join-Path $packageRoot $relativePath
            New-Item -ItemType Directory -Path (Split-Path $destinationPath) -Force | Out-Null
            Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
        }
    }

    New-Item -ItemType Directory -Path (Join-Path $packageRoot 'log') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $packageRoot 'config\weekly_schedule') -Force | Out-Null

    $forbiddenFiles = Get-ChildItem -LiteralPath (Join-Path $packageRoot 'config') -File -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Extension -in @('.ini', '.crt')) -or
            ($_.Extension -eq '.json' -and $_.BaseName -notlike 'template*') -or
            ($_.Extension -eq '.yaml' -and $_.Name -notlike 'deploy.*.yaml')
        }
    if ($forbiddenFiles) {
        throw "Personal configuration files entered the package: $($forbiddenFiles.Name -join ', ')"
    }

    $archiveName = "OnmyojiAutoScript-testoyj-$Version-Windows.zip"
    $releaseArchive = Join-Path $outputPath $archiveName
    if (Test-Path -LiteralPath $releaseArchive) {
        Remove-Item -LiteralPath $releaseArchive -Force
    }

    Push-Location $workRoot
    try {
        Invoke-NativeCommand -FailureMessage 'Failed to compress the Windows package' -Command {
            & 7z.exe a -tzip -mx=7 $releaseArchive $packageName
        }
    }
    finally {
        Pop-Location
    }

    $hash = (Get-FileHash -LiteralPath $releaseArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumPath = "$releaseArchive.sha256"
    Set-Content -LiteralPath $checksumPath -Value "$hash  $archiveName" -Encoding ascii

    Write-Host "Package: $releaseArchive"
    Write-Host "Checksum: $checksumPath"
    Write-Host "Commit: $packageCommit"
}
finally {
    if ($workRoot.StartsWith([System.IO.Path]::GetTempPath(), [System.StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $workRoot)) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
}
