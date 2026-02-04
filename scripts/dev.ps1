# Resonance Development Script
# Starts both Python backend and Svelte frontend

Write-Host "🎵 Starting Resonance Development Environment" -ForegroundColor Magenta
Write-Host ""

$ResonanceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ResonanceRoot)
{
    $ResonanceRoot = "C:\Users\stephan\Desktop\resonance"
}

$BackendPath = $ResonanceRoot
$FrontendPath = Join-Path $ResonanceRoot "web-ui"
$MambaEnv = Join-Path $ResonanceRoot ".build\mamba\envs\resonance-env"

# Check if paths exist
if (-not (Test-Path $FrontendPath))
{
    Write-Host "❌ Frontend path not found: $FrontendPath" -ForegroundColor Red
    exit 1
}

Write-Host "📂 Backend:  $BackendPath" -ForegroundColor Cyan
Write-Host "📂 Frontend: $FrontendPath" -ForegroundColor Cyan
Write-Host ""

# Start Backend in new window
Write-Host "🐍 Starting Python Backend (Port 9000)..." -ForegroundColor Yellow
$backendCmd = "micromamba run -p `"$MambaEnv`" python -m resonance --verbose"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$BackendPath`"; Write-Host 'Backend starting...' -ForegroundColor Green; $backendCmd" -WorkingDirectory $BackendPath

# Wait a bit for backend to start
Start-Sleep -Seconds 2

# Start Frontend in new window
Write-Host "⚡ Starting Svelte Frontend (Port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$FrontendPath`"; Write-Host 'Frontend starting...' -ForegroundColor Green; npm run dev -- --host" -WorkingDirectory $FrontendPath

# Wait a bit for frontend to start
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "✅ Development servers started!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "🔌 Backend:  http://localhost:9000" -ForegroundColor Cyan
Write-Host "❤️  Health:   http://localhost:9000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to open the frontend in your browser..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Open browser
Start-Process "http://localhost:5173"
