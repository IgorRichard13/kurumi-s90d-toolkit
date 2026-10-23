# Serves src/ at http://localhost:8765 so the layout can be checked in a PC browser.
# Remote keys in the browser: arrows, Enter, Esc (Back), r (red), g (green), y (yellow).
param([int]$Port = 8765)
$root = (Resolve-Path (Join-Path $PSScriptRoot 'src')).Path
$types = @{ '.html'='text/html; charset=utf-8'; '.css'='text/css'; '.js'='application/javascript';
            '.json'='application/json'; '.png'='image/png'; '.jpg'='image/jpeg'; '.jpeg'='image/jpeg';
            '.webp'='image/webp'; '.svg'='image/svg+xml' }
$l = New-Object System.Net.HttpListener
$l.Prefixes.Add("http://localhost:$Port/")
$l.Start()
Write-Host "Abra http://localhost:$Port  (Ctrl+C para parar)"
while ($l.IsListening) {
    $ctx = $l.GetContext()
    $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
    if (-not $rel) { $rel = 'index.html' }
    $file = [IO.Path]::GetFullPath((Join-Path $root $rel))
    $res = $ctx.Response
    if ($file.StartsWith($root) -and (Test-Path $file -PathType Leaf)) {
        $bytes = [IO.File]::ReadAllBytes($file)
        $ext = [IO.Path]::GetExtension($file).ToLower()
        $res.ContentType = $(if ($types[$ext]) { $types[$ext] } else { 'application/octet-stream' })
        $res.Headers.Add('Cache-Control', 'no-store')
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
    } else { $res.StatusCode = 404 }
    $res.Close()
}
