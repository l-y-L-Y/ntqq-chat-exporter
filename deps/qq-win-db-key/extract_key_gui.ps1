param(
    [Parameter(Mandatory = $true)][string]$ScriptPath,
    [Parameter(Mandatory = $true)][string]$QQExePath,
    [Parameter(Mandatory = $true)][string]$WrapperNodePath
)

$ErrorActionPreference = 'Stop'
$source = [System.IO.File]::ReadAllText($ScriptPath, [System.Text.Encoding]::UTF8)
$qqLiteral = $QQExePath.Replace("'", "''")
$injection = '$qqInfo = @{ QQExePath = ''' + $qqLiteral + ''' }' + [Environment]::NewLine + 'if (-not $qqInfo) {'
$source = $source.Replace('if (-not $qqInfo) {', $injection)
$scriptBlock = [ScriptBlock]::Create($source)
$output = & $scriptBlock -WrapperNodePath $WrapperNodePath 6>&1
$candidates = @()
foreach ($item in $output) {
    $line = $item.ToString()
    $match = [regex]::Match($line, ':\s*(?<key>[ -~]{16})\s*$')
    if ($match.Success) { $candidates += $match.Groups['key'].Value }
}
if ($candidates.Count -gt 0) { [Console]::Out.Write($candidates[$candidates.Count - 1]) }
