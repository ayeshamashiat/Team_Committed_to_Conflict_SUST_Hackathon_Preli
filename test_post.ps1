# test_post.ps1 — uses Python stdlib to avoid all curl quoting issues
$ErrorActionPreference = "Stop"

Write-Host "`n--- /health ---" -ForegroundColor Cyan
python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
Write-Host ""

Write-Host "`n--- /analyze-ticket ---" -ForegroundColor Cyan
python -c "import urllib.request, json; req=urllib.request.Request('http://localhost:8000/analyze-ticket', data=open('sample_input.json','rb').read(), headers={'Content-Type':'application/json'}); print(json.dumps(json.loads(urllib.request.urlopen(req).read().decode()), indent=2, ensure_ascii=False))"
Write-Host ""