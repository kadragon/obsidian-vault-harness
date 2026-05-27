$raw = [Console]::In.ReadToEnd()
$d = $raw | ConvertFrom-Json
$fp = $d.tool_input.file_path
if ($fp -and $fp -match '\.md$' -and (Test-Path $fp)) {
    $bad = @(Get-Content $fp -Encoding UTF8 | Where-Object { $_ -match '- \[ \]' -and $_ -notmatch '📅' })
    if ($bad.Count -gt 0) {
        $lines = ($bad | ForEach-Object { "  $_" }) -join "`n"
        $msg = "⚠️ 마감일(📅) 없는 할일 발견:`n$lines`n→ 📅 YYYY-MM-DD 추가 필요"
        @{ hookSpecificOutput = @{ hookEventName = 'PostToolUse'; additionalContext = $msg } } | ConvertTo-Json -Compress
    }
}
