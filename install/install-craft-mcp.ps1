#Requires -Version 5.1
<#
.SYNOPSIS
    Craft MCP installer idempotente multi-client (per-utente, nessun admin).

.DESCRIPTION
    Registra due famiglie di server MCP nei client rilevati, PRESERVANDO i server
    gia' configurati:

      A) ArtCraft generativo  -> artcraft-mcp.exe            (61 tool, cloud)
      B) Crafting Apps suite  -> "<App>\<app>-cli.exe" mcp   (una entry per app)
         CADCraft, DeckCraft, DesignCraft, EffectCraft, FilmCraft, GridCraft,
         LightCraft, PdfCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft

    Client gestiti:
      - Freebuff        : ~\.agents\mcp.json                          (merge JSON)
      - Claude Desktop  : %APPDATA%\Claude\claude_desktop_config.json (merge JSON)
      - Antigravity     : ~\.gemini\config\mcp_config.json            (merge JSON)
      - Claude Code     : via CLI `claude mcp add --scope user`
      - dsh / Codex     : NON automatizzati (istruzioni a fine esecuzione)

    Sicurezza: nessun privilegio amministrativo, backup .bak.<timestamp> prima di
    ogni scrittura, idempotente.

.PARAMETER SourceBin
    Binario dell'MCP generativo ArtCraft.

.PARAMETER InstallDir
    Cartella stabile di destinazione (default: %LOCALAPPDATA%\Programs\artcraft-mcp).

.PARAMETER ProxyScript
    Script Python (artcraft-mcp-proxy.py) da usare come shim di conformita' MCP per
    l'MCP generativo. Se indicato, viene copiato nella cartella di installazione e
    l'entry 'artcraft' diventa: python <proxy>. Risolve il difetto snake_case.

.PARAMETER PythonExe
    Interprete Python da usare per il proxy (default: quello nel PATH).

.PARAMETER SkipGenerative
    Non registrare l'MCP generativo ArtCraft.

.PARAMETER SkipSuite
    Non registrare gli MCP delle Crafting Apps.

.PARAMETER DryRun
    Mostra cosa verrebbe fatto senza scrivere nulla.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install-craft-mcp.ps1 -DryRun
    powershell -ExecutionPolicy Bypass -File .\install-craft-mcp.ps1
#>
[CmdletBinding()]
param(
    [string] $SourceBin = 'C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0\bin\artcraft-mcp.exe',
    [string] $InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\artcraft-mcp'),
    [string] $ProxyScript = '',
    [string] $PythonExe = '',
    [switch] $SkipGenerative,
    [switch] $SkipSuite,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$summary = New-Object System.Collections.Generic.List[object]
$registered = 0

function Write-Log   { param([string]$m) Write-Host $m }
function Write-Warn2 { param([string]$m) Write-Host $m -ForegroundColor Yellow }
function Fail        { param([string]$m) Write-Host "ERRORE: $m" -ForegroundColor Red; exit 1 }

Write-Log "=== Craft MCP - installer ==="
if ($DryRun) { Write-Warn2 "[DRY-RUN] nessuna scrittura verra' eseguita`n" }

# ------------------------------------------------------------ 1. MCP generativo
$binPath = $null
if (-not $SkipGenerative) {
    if (-not (Test-Path -LiteralPath $SourceBin)) { Fail "binario sorgente non trovato: $SourceBin" }
    $binPath = Join-Path $InstallDir 'artcraft-mcp.exe'
    if ($DryRun) {
        Write-Log "[DRY-RUN] copierebbe: $SourceBin  ->  $binPath"
    } else {
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Copy-Item -LiteralPath $SourceBin -Destination $binPath -Force
    }
    if (Test-Path -LiteralPath $binPath) {
        Write-Log ("Binario : {0}" -f $binPath)
        Write-Log ("SHA256  : {0}" -f (Get-FileHash -LiteralPath $binPath -Algorithm SHA256).Hash)
    }

    # shim di conformita' MCP: l'entry 'artcraft' passa per il proxy Python
    $generativeCommand = $binPath
    $generativeArgs = @()
    if ($ProxyScript -ne '') {
        if (-not (Test-Path -LiteralPath $ProxyScript)) { Fail ("proxy non trovato: {0}" -f $ProxyScript) }
        if ($PythonExe -eq '') {
            $py = Get-Command python -ErrorAction SilentlyContinue
            if (-not $py) { Fail "python non trovato nel PATH: indica -PythonExe" }
            $PythonExe = $py.Source
        }
        if (-not (Test-Path -LiteralPath $PythonExe)) { Fail ("interprete Python non trovato: {0}" -f $PythonExe) }
        $proxyDst = Join-Path $InstallDir 'artcraft-mcp-proxy.py'
        if ($DryRun) { Write-Log ("[DRY-RUN] copierebbe: {0}  ->  {1}" -f $ProxyScript, $proxyDst) }
        else { Copy-Item -LiteralPath $ProxyScript -Destination $proxyDst -Force }
        $generativeCommand = $PythonExe
        $generativeArgs = @($proxyDst)
        Write-Log ("Proxy   : {0} `"{1}`"" -f $PythonExe, $proxyDst)
    }
}

# ------------------------------------------- 2. inventario Crafting Apps
$SuiteApps = [ordered]@{
    cadcraft    = 'CADCraft'
    deckcraft   = 'DeckCraft'
    designcraft = 'DesignCraft'
    effectcraft = 'EffectCraft'
    filmcraft   = 'FilmCraft'
    gridcraft   = 'GridCraft'
    lightcraft  = 'LightCraft'
    pdfcraft    = 'PdfCraft'
    photocraft  = 'PhotoCraft'
    soundcraft  = 'SoundCraft'
    vectorcraft = 'VectorCraft'
    wordcraft   = 'WordCraft'
}

$suiteServers = New-Object System.Collections.Generic.List[object]
if (-not $SkipSuite) {
    $pf = $env:ProgramFiles
    foreach ($key in $SuiteApps.Keys) {
        $folder = $SuiteApps[$key]
        $exe = Join-Path $pf "$folder\$key-cli.exe"
        if (Test-Path -LiteralPath $exe) {
            $suiteServers.Add([pscustomobject]@{ Name = $key; Exe = $exe })
        } else {
            Write-Warn2 ("Suite: SKIP {0} (non trovato: {1})" -f $key, $exe)
        }
    }
    Write-Log ("Crafting Apps rilevate: {0}" -f $suiteServers.Count)
}

# ------------------------------------------------- 3. merge JSON idempotente
function Set-McpJsonEntry {
    param(
        [Parameter(Mandatory)][string]   $ConfigPath,
        [Parameter(Mandatory)][string]   $Name,
        [Parameter(Mandatory)][string]   $Command,
        [string[]] $Arguments = @()
    )
    $dir = Split-Path -Parent $ConfigPath
    if (-not (Test-Path -LiteralPath $dir)) {
        Write-Log ("SKIP  (client non installato): {0}" -f $ConfigPath)
        return [pscustomobject]@{ Client = $ConfigPath; Result = 'absent' }
    }

    $existed = Test-Path -LiteralPath $ConfigPath
    if ($existed) {
        $raw = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { $obj = New-Object psobject }
        else {
            try { $obj = $raw | ConvertFrom-Json }
            catch { Fail ("JSON non valido in {0} ({1}): nessuna modifica fatta" -f $ConfigPath, $_.Exception.Message) }
        }
    } else {
        $obj = New-Object psobject
        Write-Log ("NUOVO file: {0}" -f $ConfigPath)
    }

    if (-not $obj.PSObject.Properties['mcpServers']) {
        $obj | Add-Member -MemberType NoteProperty -Name 'mcpServers' -Value (New-Object psobject)
    }
    if ($null -eq $obj.mcpServers) { $obj.mcpServers = New-Object psobject }

    $existing = $obj.mcpServers.PSObject.Properties[$Name]
    if ($existing) {
        if ($existing.Value.command -eq $Command) {
            return [pscustomobject]@{ Client = $ConfigPath; Result = 'unchanged'; Name = $Name }
        }
        $action = 'updated'
    } else {
        $action = 'added'
    }

    $entry = New-Object psobject
    $entry | Add-Member NoteProperty 'type'    'stdio'
    $entry | Add-Member NoteProperty 'command' $Command
    $entry | Add-Member NoteProperty 'args'    ([string[]]$Arguments)
    $entry | Add-Member NoteProperty 'env'     (New-Object psobject)

    $obj.mcpServers | Add-Member -MemberType NoteProperty -Name $Name -Value $entry -Force
    $script:registered++

    if (-not $DryRun) {
        if ($existed) { Copy-Item -LiteralPath $ConfigPath -Destination "$ConfigPath.bak.$stamp" -Force }
        $json = $obj | ConvertTo-Json -Depth 100
        [System.IO.File]::WriteAllText($ConfigPath, $json, $utf8NoBom)
    }
    Write-Log ("{0,-5} {1}  ->  {2}" -f $action.ToUpper(), $Name, $ConfigPath)
    return [pscustomobject]@{ Client = $ConfigPath; Result = $action; Name = $Name }
}

# client JSON: Freebuff (crea), Claude Desktop, Antigravity
$jsonTargets = @(
    (Join-Path $env:USERPROFILE '.agents\mcp.json'),
    (Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'),
    (Join-Path $env:USERPROFILE '.gemini\config\mcp_config.json')
)

# server da registrare: generativo + suite
$servers = New-Object System.Collections.Generic.List[object]
if ($null -ne $binPath) { $servers.Add([pscustomobject]@{ Name = 'artcraft'; Exe = $generativeCommand; Args = $generativeArgs }) }
foreach ($s in $suiteServers) { $servers.Add([pscustomobject]@{ Name = $s.Name; Exe = $s.Exe; Args = @('mcp') }) }

Write-Log "`n--- Client JSON ---"
foreach ($t in $jsonTargets) {
    foreach ($s in $servers) {
        $r = Set-McpJsonEntry -ConfigPath $t -Name $s.Name -Command $s.Exe -Arguments $s.Args
        $summary.Add($r)
    }
}

# ------------------------------------------- 4. Claude Code (via CLI)
$claude = Get-Command claude -ErrorAction SilentlyContinue
Write-Log "`n--- Claude Code ---"
if (-not $claude) {
    Write-Warn2 "SKIP (CLI 'claude' non trovata)"
} else {
    foreach ($s in $servers) {
        $wantArgs = ($s.Args -join ' ')
        $present = $false
        $current = ''
        try { $current = (& $claude.Source mcp get $s.Name 2>&1 | Out-String); if ($LASTEXITCODE -eq 0) { $present = $true } } catch { }
        if ($present) {
            $curCmd = ''
            $curArgs = ''
            $cm = [regex]::Match($current, '(?m)^\s*Command:\s*(.+?)\s*$')
            $am = [regex]::Match($current, '(?m)^\s*Args:\s*(.*?)\s*$')
            if ($cm.Success) { $curCmd = $cm.Groups[1].Value.Trim() }
            if ($am.Success) { $curArgs = $am.Groups[1].Value.Trim() }
            if ($curCmd -eq $s.Exe -and $curArgs -eq $wantArgs) {
                Write-Log ("OK    {0} (gia' presente, invariato)" -f $s.Name)
                $summary.Add([pscustomobject]@{ Client = 'Claude Code'; Result = 'unchanged'; Name = $s.Name })
                continue
            }
            Write-Log ("UPD   {0} (configurazione diversa: rimuove e ri-registra)" -f $s.Name)
            if ($DryRun) {
                $summary.Add([pscustomobject]@{ Client = 'Claude Code'; Result = 'dry-run'; Name = $s.Name })
                continue
            }
            & $claude.Source mcp remove $s.Name -s user 2>&1 | Out-Null
        }
        if ($DryRun) {
            Write-Log ("[DRY-RUN] claude mcp add --scope user {0} -- `"{1}`" {2}" -f $s.Name, $s.Exe, ($s.Args -join ' '))
            $summary.Add([pscustomobject]@{ Client = 'Claude Code'; Result = 'dry-run'; Name = $s.Name })
            continue
        }
        if ($s.Args.Count -gt 0) { & $claude.Source mcp add --scope user $s.Name -- $s.Exe @($s.Args) }
        else { & $claude.Source mcp add --scope user $s.Name -- $s.Exe }
        if ($LASTEXITCODE -eq 0) {
            Write-Log ("ADD   {0} (scope utente)" -f $s.Name)
            $summary.Add([pscustomobject]@{ Client = 'Claude Code'; Result = 'added'; Name = $s.Name })
            $registered++
        } else {
            Write-Warn2 ("Claude Code: '{0}' ha restituito codice {1}" -f $s.Name, $LASTEXITCODE)
            $summary.Add([pscustomobject]@{ Client = 'Claude Code'; Result = ("failed({0})" -f $LASTEXITCODE); Name = $s.Name })
        }
    }
}

# ------------------------------------------------------------- 5. riepilogo
Write-Log "`n=== Riepilogo ==="
$summary | Group-Object Client | ForEach-Object {
    $added = ($_.Group | Where-Object { $_.Result -in @('added', 'updated') }).Count
    $same = ($_.Group | Where-Object { $_.Result -eq 'unchanged' }).Count
    Write-Log ("{0,-55} added={1,-3} unchanged={2}" -f $_.Name, $added, $same)
}

Write-Warn2 @"
Server configurati: $($servers.Count)  (generativo + suite Crafting Apps)
Backup in caso di problemi: file *.bak.$stamp accanto a ogni config.

NON automatizzati:
  * dsh (DeepSeek Harness): aggiungi i server dalla UI di dsh (scrive cordis.patch.yml).
  * Codex: %USERPROFILE%\.codex\config.toml -> [mcp_servers.<nome>]  (Codex non installato).

ArtCraft generativo: le credenziali NON sono presenti.
  Crea %USERPROFILE%\Artcraft\credentials\artcraft_session.txt e artcraft_avt.txt
  (oppure imposta ARTCRAFT_API_KEY). Senza credenziali il server risponde ma i tool
  di generazione falliscono in autenticazione.

Le Crafting Apps sono locali e non richiedono credenziali ArtCraft.
"@
