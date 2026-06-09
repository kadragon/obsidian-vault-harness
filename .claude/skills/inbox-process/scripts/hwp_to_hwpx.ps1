# hwp_to_hwpx.ps1
# Usage: .\hwp_to_hwpx.ps1 -InboxPath "C:\Dev\ObsidianVault\01_Inbox"
# Converts all .hwp files under InboxPath to .hwpx via Hancom COM automation.
# Deletes original .hwp on success. Prints OK/FAIL per file.
# Exits 0 on success or no files found. Exits 1 if Hancom COM unavailable.

param(
    [Parameter(Mandatory)][string]$InboxPath
)

$hwpFiles = Get-ChildItem -Path $InboxPath -Filter "*.hwp" -Recurse -ErrorAction SilentlyContinue

if (-not $hwpFiles) {
    Write-Output "SKIP: no .hwp files found"
    exit 0
}

try {
    $hwp = New-Object -ComObject "HWPFrame.HwpObject" -ErrorAction Stop
} catch {
    Write-Output "ERROR: Hancom not installed or COM registration missing"
    exit 1
}

$hwp.SetMessageBoxMode(65535) | Out-Null

foreach ($file in $hwpFiles) {
    $in  = $file.FullName
    $out = $in -replace '\.hwp$', '.hwpx'

    try {
        $hwp.Open($in, "HWP", "forceopen:true") | Out-Null
        $saved = $hwp.SaveAs($out, "HWPX", "")
        if ($saved -and (Test-Path $out)) {
            Remove-Item $in -Force
            Write-Output "OK: $($file.Name)"
        } else {
            Write-Output "FAIL: $($file.Name) (SaveAs returned false)"
        }
    } catch {
        Write-Output "FAIL: $($file.Name) ($_)"
    }
}

try { $hwp.Quit() } catch {}
