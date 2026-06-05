try {
    $raw = [Console]::In.ReadToEnd()
    $d = $raw | ConvertFrom-Json
} catch { exit 0 }

$fp = $d.tool_input.file_path
if (-not $fp) { exit 0 }

# Skip templates, docs, harness files, archive, and root planning files
if ($fp -match '99_Template|\\docs\\|\.claude\\|90_Archive|backlog\.md|tasks\.md') { exit 0 }

if ($fp -match '\.md$' -and (Test-Path $fp)) {
    $calEmoji = [char]::ConvertFromUtf32(0x1F4C5)  # 📅
    $bad = @(Get-Content $fp -Encoding UTF8 | Where-Object { $_ -match '- \[ \]' -and $_ -notmatch [regex]::Escape($calEmoji) })
    if ($bad.Count -gt 0) {
        $lines = ($bad | ForEach-Object { "  $_" }) -join "`n"
        $msg = "[WARNING] due date 없는 할일 발견:`n$lines`n-> 📅 YYYY-MM-DD 추가 필요"
        @{ hookSpecificOutput = @{ hookEventName = 'PostToolUse'; additionalContext = $msg } } | ConvertTo-Json -Compress
    }
}
