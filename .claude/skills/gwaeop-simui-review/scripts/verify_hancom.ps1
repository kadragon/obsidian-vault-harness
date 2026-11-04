# Open an .hwpx in Hancom (hidden) via a probe copy and report whether it loads.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File verify_hancom.ps1 <file.hwpx>
# Prints "open=<bool> pages=<n> memos=<n>". Exit 0 only when Hancom opens it.
# Works on a temp copy: Hancom COM can rewrite the file it opened (see auto-memory
# feedback-hancom-com-original-overwrite), so the target is never opened directly.
param([Parameter(Mandatory = $true)][string]$Path)

$src = (Resolve-Path -LiteralPath $Path).Path
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("hwpx_probe_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$probe = Join-Path $tmp "probe.hwpx"
$resaved = Join-Path $tmp "resaved.hwpx"
Copy-Item -LiteralPath $src -Destination $probe

$hwp = New-Object -ComObject HWPFrame.HwpObject
try {
    $hwp.XHwpWindows.Item(0).Visible = $false
    $hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule") | Out-Null
    $ok = $hwp.Open($probe, "HWPX", "forceopen:true")
    $pages = $hwp.PageCount
    $memos = 0
    if ($ok -and $hwp.SaveAs($resaved, "HWPX", "")) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($resaved)
        try {
            foreach ($e in $zip.Entries | Where-Object { $_.FullName -like "Contents/section*.xml" }) {
                $reader = New-Object IO.StreamReader($e.Open())
                $memos += ([regex]::Matches($reader.ReadToEnd(), 'type="MEMO"')).Count
                $reader.Close()
            }
        } finally { $zip.Dispose() }
    }
    "open=$ok pages=$pages memos=$memos"
} finally {
    $hwp.Clear(1)
    $hwp.Quit()
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
if ($ok) { exit 0 } else { exit 1 }
