# Opens the report in Word, fills the TOC page numbers from the laid-out heading positions,
# saves, and exports a PDF copy. Usage: powershell -File finalize_report.ps1 <docx> <pdf>
param([string]$Docx, [string]$Pdf)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx)
    $doc.Repaginate()
    # heading text -> page number (adjusted for section restarts)
    $pages = @{}
    foreach ($p in $doc.Paragraphs) {
        if ($p.OutlineLevel -le 3) {
            $t = $p.Range.Text.Trim()
            if ($t -and -not $pages.ContainsKey($t)) { $pages[$t] = $p.Range.Information(1) }
        }
    }
    $toc = $null
    foreach ($t in $doc.Tables) {
        if ($t.Range.Text -match "Page No\.") { $toc = $t; break }
    }
    if (-not $toc) { throw "TOC table not found" }
    $missing = @()
    for ($r = 2; $r -le $toc.Rows.Count; $r++) {
        $c1 = ($toc.Cell($r, 1).Range.Text -replace "[\r\a]", "").Trim()
        $c2 = ($toc.Cell($r, 2).Range.Text -replace "[\r\a]", "").Trim()
        $c3 = $toc.Cell($r, 3).Range
        if (-not ($c3.Text -match "@@")) { continue }
        $key = if ($c1) { "$c1 $c2" } else { $c2 }
        if ($pages.ContainsKey($key)) {
            $f = $c3.Find
            [void]$f.Execute("@@", $false, $false, $false, $false, $false, $true, 0, $false, [string]$pages[$key], 2)
        } else { $missing += $key }
    }
    if ($missing.Count) { Write-Output ("unmatched TOC rows: " + ($missing -join " | ")) }
    $doc.Save()
    $doc.ExportAsFixedFormat($Pdf, 17)
    Write-Output ("pages: " + $doc.ComputeStatistics(2))
    $doc.Close($false)
} finally {
    $word.Quit()
}
