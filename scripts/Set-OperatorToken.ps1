param(
    [string]$Path = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env.local")
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$examplePath = Join-Path $projectRoot ".env.example"
$targetPath = [System.IO.Path]::GetFullPath($Path)

if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
    Copy-Item -LiteralPath $examplePath -Destination $targetPath
}

$content = [System.IO.File]::ReadAllText($targetPath)
$token = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
if ($content -match '(?m)^OPERATOR_API_TOKEN=.*$') {
    $content = [regex]::Replace($content, '(?m)^OPERATOR_API_TOKEN=.*$', "OPERATOR_API_TOKEN=$token")
}
else {
    $content = $content.TrimEnd() + [Environment]::NewLine + "OPERATOR_API_TOKEN=$token" + [Environment]::NewLine
}
[System.IO.File]::WriteAllText($targetPath, $content, [System.Text.UTF8Encoding]::new($false))
Remove-Variable token
Write-Host "Updated OPERATOR_API_TOKEN in $targetPath without printing the secret."
