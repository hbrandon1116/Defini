#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SoloActualizar,
    [switch]$Detener,
    [switch]$SinNavegador
)

$ErrorActionPreference = "Stop"
$ProjectRoot  = $PSScriptRoot
$BackendDir   = Join-Path $ProjectRoot "backend"
$FrontendDir  = Join-Path $ProjectRoot "frontend"
$VenvDir      = Join-Path $ProjectRoot ".venv"
$VenvPython   = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $BackendDir "requirements.txt"
$DatabaseFile = Join-Path $BackendDir "data\inventario.sqlite3"
$script:StartedPids = @()

function Write-Banner {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  DEFINI - MINIPROYECTO DE INVENTARIO (SPRINT 2)" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Cyan
}
function Write-Section { param([string]$Text) Write-Host ""; Write-Host ">>> $Text" -ForegroundColor Cyan }
function Write-Ok      { param([string]$Text) Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Info    { param([string]$Text) Write-Host "  $Text" -ForegroundColor Gray }
function Write-Warn    { param([string]$Text) Write-Host "  [AVISO] $Text" -ForegroundColor Yellow }
function Stop-WithError { param([string]$Text) throw $Text }

function Update-SessionPath {
    try {
        $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $user    = [Environment]::GetEnvironmentVariable("Path", "User")
        $parts   = @($machine, $user) | Where-Object { $_ }
        if ($parts.Count -gt 0) { $env:Path = (($parts | ForEach-Object { $_.TrimEnd(';') }) -join ';') }
    } catch { }
}

function Install-WithWinget {
    param([string]$Id, [string]$Name)
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { Stop-WithError "$Name no esta instalado y no se encontro winget. Instalalo manualmente." }
    Write-Warn "$Name no encontrado. Instalando con winget (puede pedir permisos de administrador)..."
    & $winget.Source install --id $Id --exact --silent --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { Stop-WithError "No se pudo instalar $Name con winget (codigo $LASTEXITCODE)." }
    Update-SessionPath
}

function Resolve-Python {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py -and $py.Source) {
        try {
            $exe = @(& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null) | Select-Object -First 1
            if ($exe -and (Test-Path $exe)) { return $exe }
        } catch { }
    }
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        "C:\Program Files\Python313",
        "C:\Program Files\Python312",
        "C:\Program Files\Python311"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $direct = Join-Path $root "python.exe"
        if (Test-Path $direct) { return $direct }
        $found = Get-ChildItem -Path $root -Filter "python.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue |
                 Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

function Resolve-Node {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:ProgramFiles "nodejs\node.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe"),
        "C:\Program Files (x86)\nodejs\node.exe"
    )
    foreach ($candidate in $candidates) { if (Test-Path $candidate) { return $candidate } }
    return $null
}

function Resolve-Npm {
    param([string]$NodeExe)
    $candidate = Join-Path (Split-Path -Parent $NodeExe) "npm.cmd"
    if (Test-Path $candidate) { return $candidate }
    $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $null
}

function Assert-PythonVersion {
    param([string]$PythonExe)
    $version = @(& $PythonExe -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" 2>$null) | Select-Object -First 1
    if (-not $version) { Stop-WithError "No se pudo ejecutar Python." }
    $p = $version.Trim().Split('.')
    if ([int]$p[0] -lt 3 -or ([int]$p[0] -eq 3 -and [int]$p[1] -lt 11)) {
        Stop-WithError "Python $version detectado; se requiere 3.11 o superior."
    }
    Write-Ok "Python $version"
}

function Assert-NodeVersion {
    param([string]$NodeExe)
    $raw = @(& $NodeExe --version 2>$null) | Select-Object -First 1
    if (-not $raw) { Stop-WithError "No se pudo ejecutar Node.js." }
    $v = $raw.Trim().TrimStart('v')
    $p = $v.Split('.')
    if ([int]$p[0] -lt 20 -or ([int]$p[0] -eq 20 -and [int]$p[1] -lt 19)) {
        Stop-WithError "Node.js $v detectado; se requiere 20.19 o superior."
    }
    Write-Ok "Node.js $v"
}

function Ensure-Runtimes {
    $python = Resolve-Python
    if (-not $python) { Install-WithWinget "Python.Python.3.12" "Python"; $python = Resolve-Python }
    if (-not $python) { Stop-WithError "Python no esta disponible en este equipo." }
    Assert-PythonVersion $python

    $node = Resolve-Node
    if (-not $node) { Install-WithWinget "OpenJS.NodeJS.LTS" "Node.js"; $node = Resolve-Node }
    if (-not $node) { Stop-WithError "Node.js no esta disponible en este equipo." }
    Assert-NodeVersion $node

    $npm = Resolve-Npm $node
    if (-not $npm) { Stop-WithError "No se encontro npm junto a Node.js." }
    $npmVersion = @(& $npm --version 2>$null) | Select-Object -First 1
    Write-Ok "npm $npmVersion"

    $nodeDir = Split-Path -Parent $node
    if (($env:Path -split ';') -notcontains $nodeDir) { $env:Path = "$nodeDir;$env:Path" }

    return [pscustomobject]@{ Python = $python; Node = $node; Npm = $npm }
}

function Ensure-Venv {
    param([string]$PythonExe)
    if (Test-Path $VenvPython) { Write-Ok "Entorno virtual .venv presente."; return }
    Write-Section "Creando entorno virtual .venv"
    & $PythonExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Stop-WithError "No se pudo crear el entorno virtual." }
    Write-Ok "Entorno virtual creado."
}

function Ensure-PythonDeps {
    $hash  = (Get-FileHash -Path $Requirements -Algorithm SHA256).Hash
    $stamp = Join-Path $VenvDir ".defini-requirements"
    $need  = $true
    if (Test-Path $stamp) {
        try { $need = ((Get-Content -Path $stamp -Raw).Trim() -ne $hash) } catch { $need = $true }
    }
    & $VenvPython -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('django') and importlib.util.find_spec('bcrypt') else 1)" 2>$null
    if ($LASTEXITCODE -ne 0) { $need = $true }

    if ($need) {
        Write-Section "Instalando dependencias de Python"
        & $VenvPython -m pip install --disable-pip-version-check --upgrade -r $Requirements
        if ($LASTEXITCODE -ne 0) { Stop-WithError "Fallo la instalacion de dependencias de Python. Verifica Internet." }
        Set-Content -Path $stamp -Value $hash -Encoding ASCII
    } else {
        Write-Ok "Dependencias de Python ya instaladas."
    }

    & $VenvPython -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('django') and importlib.util.find_spec('bcrypt') else 1)" 2>$null
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Django o bcrypt no se pudieron importar." }
    $versions = @(& $VenvPython -c "import django, bcrypt; print('Django ' + django.get_version()); print('bcrypt ' + bcrypt.__version__)" 2>$null)
    foreach ($line in $versions) { Write-Ok $line }
    $checkOut = @(& $VenvPython -m pip check 2>&1)
    $checkCode = $LASTEXITCODE
    foreach ($line in $checkOut) { Write-Info $line }
    if ($checkCode -ne 0) { Write-Warn "pip check encontro incompatibilidades (revisa las lineas anteriores)." }
}

function Ensure-NodeDeps {
    param([string]$NpmCmd)
    $pkg   = Join-Path $FrontendDir "package.json"
    $lock  = Join-Path $FrontendDir "package-lock.json"
    $modules = Join-Path $FrontendDir "node_modules"
    $stamp = Join-Path $modules ".defini-deps"
    $hash  = (Get-FileHash -Path $pkg -Algorithm SHA256).Hash
    if (Test-Path $lock) { $hash = $hash + (Get-FileHash -Path $lock -Algorithm SHA256).Hash }

    $need = $true
    if ((Test-Path $modules) -and (Test-Path $stamp)) {
        try { $need = ((Get-Content -Path $stamp -Raw).Trim() -ne $hash) } catch { $need = $true }
    }
    foreach ($required in @("vite", "react", "react-dom", "@tanstack\react-query")) {
        if (-not (Test-Path (Join-Path $modules "$required\package.json"))) { $need = $true }
    }

    if ($need) {
        Write-Section "Instalando dependencias del frontend"
        Push-Location $FrontendDir
        try {
            & $NpmCmd install --no-audit --no-fund --prefer-offline
            if ($LASTEXITCODE -ne 0) { Stop-WithError "Fallo npm install. Verifica Internet y vuelve a intentar." }
        } finally { Pop-Location }
        if (-not (Test-Path (Join-Path $modules "vite\package.json"))) { Stop-WithError "Vite no quedo instalado." }
        Set-Content -Path $stamp -Value $hash -Encoding ASCII
    } else {
        Write-Ok "Dependencias del frontend ya instaladas."
    }
}

function Show-NpmOutdated {
    param([string]$NpmCmd)
    Push-Location $FrontendDir
    try {
        $raw = @(& $NpmCmd outdated --json --silent --fetch-timeout=5000 --fetch-retries=0 2>$null)
        if ($LASTEXITCODE -eq 1 -and $raw.Count -gt 0) {
            $text = (($raw -join "`n").Trim())
            if ($text) {
                try {
                    $data = $text | ConvertFrom-Json
                    $names = @($data.PSObject.Properties | ForEach-Object { $_.Name })
                    if ($names.Count -gt 0) {
                        Write-Warn "Hay $($names.Count) paquete(s) con versiones nuevas disponibles."
                        $names | Select-Object -First 8 | ForEach-Object {
                            $item = $data.$_
                            Write-Info "  - $_ : $($item.current) -> $($item.wanted) (ultima: $($item.latest))"
                        }
                        if ($names.Count -gt 8) { Write-Info "  ... y $($names.Count - 8) mas." }
                        Write-Info "Actualizar-Defini.bat aplica las compatibles (wanted). Las versiones mayores requieren revisar package.json."
                    }
                } catch { }
            }
        }
    } catch { } finally { Pop-Location }
}

function Initialize-Database {
    Write-Section "Preparando la base de datos"
    $previous = $env:INVENTARIO_INIT_ONLY
    $env:INVENTARIO_INIT_ONLY = "1"
    $output = @()
    $code = 0
    Push-Location $BackendDir
    try {
        $output = @(& $VenvPython run.py 2>&1)
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
        if ($null -eq $previous) { Remove-Item Env:\INVENTARIO_INIT_ONLY -ErrorAction SilentlyContinue }
        else { $env:INVENTARIO_INIT_ONLY = $previous }
    }
    foreach ($line in $output) { if ($null -ne $line) { Write-Host "  $line" -ForegroundColor DarkGray } }
    if ($code -ne 0) { Stop-WithError "No se pudo preparar la base de datos (codigo $code)." }

    $passLine = @($output) | Where-Object { "$_" -match "temporal" } | Select-Object -First 1
    if ($passLine) {
        Write-Host ""
        Write-Host "  CONTRASENA TEMPORAL DEL ADMINISTRADOR:" -ForegroundColor Yellow
        Write-Host "  $passLine" -ForegroundColor Yellow
        Write-Host "  Guardala antes de cerrar esta ventana." -ForegroundColor Yellow
        Write-Host ""
    }

    if (-not (Test-Path $DatabaseFile)) { Stop-WithError "No se encontro la base de datos en backend\data." }
    $pyCode = "import sqlite3,sys,json; c=sqlite3.connect(sys.argv[1]); q=c.execute('PRAGMA quick_check').fetchone()[0]; print(json.dumps({'check':q,'users':c.execute('select count(*) from users').fetchone()[0],'categories':c.execute('select count(*) from categories').fetchone()[0],'products':c.execute('select count(*) from products').fetchone()[0]}))"
    $raw = @(& $VenvPython -c $pyCode $DatabaseFile 2>$null) | Select-Object -First 1
    if ($raw) {
        try {
            $info = $raw | ConvertFrom-Json
            if ($info.check -ne "ok") { Stop-WithError "La base de datos reporto un problema de integridad: $($info.check)" }
            Write-Ok "Base de datos integra: $($info.users) usuarios, $($info.categories) tipos, $($info.products) productos."
        } catch { Write-Warn "No se pudo verificar la base de datos: $($_.Exception.Message)" }
    }
}

function Get-PortProcess {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $conn) { return $null }
    return Get-CimInstance Win32_Process -Filter ("ProcessId=" + $conn.OwningProcess) -ErrorAction SilentlyContinue
}

function Get-ProcessChain {
    param([int]$ProcessId)
    $chain = @()
    $current = $ProcessId
    for ($i = 0; $i -lt 6 -and $current -gt 0; $i++) {
        $item = Get-CimInstance Win32_Process -Filter "ProcessId=$current" -ErrorAction SilentlyContinue
        if ($null -eq $item) { break }
        if ($item.Name -match '^(?i)(powershell|pwsh|cmd|windowsterminal|openconsole|explorer)\.exe$') { break }
        $chain += $item
        $current = [int]$item.ParentProcessId
    }
    return $chain
}

function Test-ProjectProcess {
    param([int]$ProcessId)
    foreach ($item in @(Get-ProcessChain $ProcessId)) {
        $cmd = [string]$item.CommandLine
        $exe = [string]$item.ExecutablePath
        if ($cmd -and $cmd.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
        if ($exe -and $exe.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    }
    return $false
}

function Get-ProjectTopProcessId {
    param([int]$ProcessId)
    $top = $ProcessId
    foreach ($item in @(Get-ProcessChain $ProcessId)) {
        $cmd = [string]$item.CommandLine
        $exe = [string]$item.ExecutablePath
        if (($cmd -and $cmd.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0) -or
            ($exe -and $exe.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0)) {
            $top = [int]$item.ProcessId
        }
    }
    return $top
}

function Stop-ProjectTree {
    param([int]$ProcessId)
    $top = Get-ProjectTopProcessId $ProcessId
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & taskkill.exe /PID $top /T /F 2>$null | Out-Null
        Start-Sleep -Milliseconds 400
        if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
            Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        }
    } finally {
        $ErrorActionPreference = $previousEap
    }
}

function Clear-ProjectPort {
    param([int]$Port, [string]$Name)
    $proc = Get-PortProcess $Port
    if ($null -eq $proc) { return }
    if (-not (Test-ProjectProcess $proc.ProcessId)) {
        Stop-WithError "El puerto $Port esta ocupado por '$($proc.Name)' (PID $($proc.ProcessId)), que no es de este proyecto. Cierralo y reintenta."
    }
    Write-Warn "Deteniendo instancia anterior de $Name (PID $($proc.ProcessId))..."
    Stop-ProjectTree $proc.ProcessId
    $deadline = (Get-Date).AddSeconds(6)
    while ((Get-Date) -lt $deadline) {
        if ($null -eq (Get-PortProcess $Port)) { break }
        Start-Sleep -Milliseconds 300
    }
    if ($null -ne (Get-PortProcess $Port)) { Stop-WithError "No se pudo liberar el puerto $Port." }
}

function Close-OldWindows {
    Get-Process -Name cmd -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -match '^Defini (Backend|Frontend)' } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}

function Wait-Http {
    param([string]$Url, [int]$Seconds, [int[]]$OkCodes)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($OkCodes -contains [int]$response.StatusCode) { return $true }
        } catch {
            $resp = $_.Exception.Response
            if ($null -ne $resp) {
                try { if ($OkCodes -contains [int]$resp.StatusCode) { return $true } } catch { }
            }
        }
        Start-Sleep -Milliseconds 600
    }
    return $false
}

function Assert-LanBinding {
    param([int]$Port, [string]$Name)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $conn) { return }
    if ($conn.LocalAddress -eq "0.0.0.0" -or $conn.LocalAddress -eq "::") {
        Write-Ok "$Name escucha en todas las interfaces (modo LAN activo)."
    } else {
        Write-Warn "$Name parece escuchar solo en local ($($conn.LocalAddress))."
    }
}

function Get-LanAddresses {
    $addresses = @()
    try {
        $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1
        if ($route) {
            $primary = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
                       Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } | Select-Object -First 1
            if ($primary) { $addresses += $primary.IPAddress }
        }
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
            ForEach-Object { if ($addresses -notcontains $_.IPAddress) { $addresses += $_.IPAddress } }
    } catch { }
    return $addresses
}

function Show-Addresses {
    $lan = @(Get-LanAddresses)
    Write-Section "Direcciones de acceso"
    Write-Host "  Local:  http://localhost:5173" -ForegroundColor White
    Write-Host "  API:    http://127.0.0.1:8080/api/" -ForegroundColor White
    if ($lan.Count -gt 0) {
        Write-Host "  LAN:" -ForegroundColor White
        foreach ($ip in $lan) { Write-Host "          http://${ip}:5173" -ForegroundColor White }
        Write-Host "  Usa la IP de tu Wi-Fi o Ethernet en los demas dispositivos." -ForegroundColor DarkGray
        Write-Host "  Si no conectan, permite Python y Node en el firewall (redes privadas)." -ForegroundColor DarkGray
    } else {
        Write-Warn "No se detecto una direccion IPv4 de red local."
    }
    Write-Host "  Base de datos: backend\data\inventario.sqlite3" -ForegroundColor DarkGray
}

function Start-Defini {
    Write-Section "Comprobando puertos"
    Clear-ProjectPort 8080 "backend"
    Clear-ProjectPort 5173 "frontend"
    Close-OldWindows
    Write-Ok "Puertos 8080 y 5173 disponibles."

    Show-Addresses

    Write-Section "Iniciando backend (salida en tiempo real)"
    $env:PYTHONUNBUFFERED = "1"
    $backend = Start-Process -FilePath $VenvPython -ArgumentList "run.py" -WorkingDirectory $BackendDir -NoNewWindow -PassThru
    $script:StartedPids += $backend.Id
    if (-not (Wait-Http "http://127.0.0.1:8080/api/auth/me" 60 @(200, 401))) {
        Stop-WithError "El backend no respondio en 60 segundos."
    }
    Write-Ok "Backend activo en http://127.0.0.1:8080"

    Write-Section "Iniciando frontend (salida en tiempo real)"
    $frontend = Start-Process -FilePath $NpmCmd -ArgumentList @("run", "dev") -WorkingDirectory $FrontendDir -NoNewWindow -PassThru
    $script:StartedPids += $frontend.Id
    if (-not (Wait-Http "http://127.0.0.1:5173/" 90 @(200))) {
        Stop-WithError "El frontend no respondio en 90 segundos."
    }
    Write-Ok "Frontend activo en http://localhost:5173"

    if (-not (Wait-Http "http://127.0.0.1:5173/api/auth/me" 20 @(200, 401))) {
        Stop-WithError "El frontend no logra comunicarse con la API."
    }
    Write-Ok "Conexion frontend -> API verificada."
    Assert-LanBinding 8080 "Backend"
    Assert-LanBinding 5173 "Frontend"

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  SERVICIOS ACTIVOS - SALIDA EN TIEMPO REAL" -ForegroundColor Green
    Write-Host "  Pulsa Ctrl+C para detener todo y cerrar esta ventana." -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
}

function Monitor-Services {
    while ($true) {
        Start-Sleep -Seconds 4
        $backendUp = $null -ne (Get-PortProcess 8080)
        $frontendUp = $null -ne (Get-PortProcess 5173)
        if (-not $backendUp -and -not $frontendUp) {
            Write-Host ""
            Write-Warn "Los servicios se detuvieron."
            break
        }
        if (-not $backendUp) {
            Write-Host ""
            Write-Warn "El backend se detuvo. Cerrando el frontend..."
            Stop-ProjectTree $script:StartedPids[1]
            break
        }
        if (-not $frontendUp) {
            Write-Host ""
            Write-Warn "El frontend se detuvo. Cerrando el backend..."
            Stop-ProjectTree $script:StartedPids[0]
            break
        }
    }
}

function Stop-Defini {
    $any = $false
    foreach ($port in @(8080, 5173)) {
        $proc = Get-PortProcess $port
        if ($null -ne $proc) {
            if (Test-ProjectProcess $proc.ProcessId) {
                Write-Warn "Deteniendo $($proc.Name) (PID $($proc.ProcessId)) en el puerto $port..."
                Stop-ProjectTree $proc.ProcessId
                $any = $true
            } else {
                Write-Warn "El puerto $port lo usa otro programa ($($proc.Name), PID $($proc.ProcessId)); no se toco."
            }
        }
    }
    Get-Process -Name cmd -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -match '^Defini (Backend|Frontend)' } |
        ForEach-Object {
            Write-Info "Cerrando ventana $($_.MainWindowTitle)..."
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $any = $true
        }
    if ($any) { Write-Ok "Servicios detenidos." } else { Write-Info "No habia servicios del proyecto en ejecucion." }
}

# ----------------------------- programa -----------------------------

try {
    if ($Detener) {
        Write-Banner
        Stop-Defini
        exit 0
    }

    Write-Banner
    Update-SessionPath

    if (-not (Test-Path (Join-Path $BackendDir "run.py"))) { Stop-WithError "No se encontro backend\run.py. La carpeta esta incompleta." }
    if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) { Stop-WithError "No se encontro frontend\package.json. La carpeta esta incompleta." }

    Write-Section "Revisando el entorno"
    $rt = Ensure-Runtimes
    $PythonExe = $rt.Python
    $NpmCmd = $rt.Npm

    Ensure-Venv $PythonExe
    Ensure-PythonDeps
    Ensure-NodeDeps $NpmCmd
    Show-NpmOutdated $NpmCmd
    Initialize-Database

    if ($SoloActualizar) {
        Write-Section "Actualizando dependencias de Python"
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install --upgrade -r $Requirements
        if ($LASTEXITCODE -ne 0) { Stop-WithError "Fallo la actualizacion de dependencias de Python." }
        Set-Content -Path (Join-Path $VenvDir ".defini-requirements") -Value (Get-FileHash -Path $Requirements -Algorithm SHA256).Hash -Encoding ASCII
        Write-Info "Las versiones de Python estan fijadas en requirements.txt; para cambiarlas edita ese archivo."

        Write-Section "Actualizando dependencias del frontend"
        Push-Location $FrontendDir
        try {
            & $NpmCmd update --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { Stop-WithError "Fallo npm update." }
        } finally { Pop-Location }
        Set-Content -Path (Join-Path $FrontendDir "node_modules\.defini-deps") -Value ((Get-FileHash -Path (Join-Path $FrontendDir "package.json") -Algorithm SHA256).Hash + (Get-FileHash -Path (Join-Path $FrontendDir "package-lock.json") -Algorithm SHA256).Hash) -Encoding ASCII

        Write-Host ""
        Write-Ok "Dependencias actualizadas correctamente."
        Write-Info "Vuelve a ejecutar Iniciar-Defini.bat para arrancar el proyecto."
        exit 0
    }

    try {
        Start-Defini
        if (-not $SinNavegador) {
            try { Start-Process "http://localhost:5173" } catch { Write-Warn "No se pudo abrir el navegador automaticamente." }
        }
        Monitor-Services
    } finally {
        Write-Host ""
        Write-Info "Deteniendo servicios..."
        foreach ($processId in $script:StartedPids) { Stop-ProjectTree $processId }
        Write-Ok "Servicios detenidos."
    }
    exit 0
}
catch {
    Write-Host ""
    Write-Host ("ERROR: " + $_.Exception.ToString()) -ForegroundColor Red
    foreach ($processId in $script:StartedPids) {
        try { & taskkill.exe /PID $processId /T /F 2>$null | Out-Null } catch { }
    }
    exit 1
}
