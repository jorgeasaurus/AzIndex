#Requires -Module Az
<#
.SYNOPSIS
    Extracts Azure PowerShell cmdlet metadata from installed Az modules and
    generates the AzIndex data files.

.DESCRIPTION
    Scans all installed Az.* modules, retrieves cmdlets via Get-Command, fetches
    help synopsis and syntax, and writes:
      public/data/manifest.json
      public/data/descriptions.json
      public/data/modules/Az.<Module>.json

.PARAMETER OutputDir
    Root of the AzIndex repository. Defaults to the parent of the scripts/ directory.

.EXAMPLE
    .\get-azcmdlets.ps1
    .\get-azcmdlets.ps1 -OutputDir C:\repos\AzIndex
#>
[CmdletBinding()]
param(
    [string]$OutputDir = (Split-Path $PSScriptRoot -Parent)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

# ── Category map ──────────────────────────────────────────────────────────────
$CategoryMap = [ordered]@{
    Accounts          = 'Authentication'
    Compute           = 'Compute'
    Network           = 'Networking'
    Storage           = 'Storage'
    Sql               = 'Database'
    CosmosDb          = 'Database'
    Redis             = 'Database'
    Monitor           = 'Monitoring'
    Advisor           = 'Governance'
    Policy            = 'Governance'
    Security          = 'Security'
    KeyVault          = 'Security'
    Identity          = 'Identity'
    Aks               = 'Containers'
    ContainerInstance = 'Containers'
    ContainerRegistry = 'Containers'
    App               = 'App Services'
    Websites          = 'App Services'
    Functions         = 'App Services'
    Logic             = 'Integration'
    ServiceBus        = 'Messaging'
    EventHub          = 'Messaging'
    EventGrid         = 'Messaging'
    NotificationHubs  = 'Messaging'
    ApiManagement     = 'API Management'
    Resources         = 'Resources'
    ResourceMover     = 'Resources'
    Cdn               = 'Networking'
    Dns               = 'Networking'
    FrontDoor         = 'Networking'
    TrafficManager    = 'Networking'
    VirtualWan        = 'Networking'
    PowerBIEmbedded   = 'Analytics'
    StreamAnalytics   = 'Analytics'
    MachineLearning   = 'AI & ML'
    CognitiveServices = 'AI & ML'
    DataFactory       = 'Data'
    DataLakeStore     = 'Data'
    Synapse           = 'Data'
    Databricks        = 'Data'
    Batch             = 'Compute'
    HDInsight         = 'Compute'
    ServiceFabric     = 'Compute'
    Automation        = 'Management'
    Backup            = 'Management'
    RecoveryServices  = 'Management'
    OperationalInsights = 'Monitoring'
}

function Get-Category([string]$ModuleName) {
    $suffix = $ModuleName -replace '^Az\.', ''
    foreach ($key in $CategoryMap.Keys) {
        if ($suffix -ieq $key) { return $CategoryMap[$key] }
    }
    foreach ($key in $CategoryMap.Keys) {
        if ($suffix -imatch $key) { return $CategoryMap[$key] }
    }
    return 'Other'
}

function Get-VerbFromName([string]$CmdletName) {
    if ($CmdletName -match '^([A-Za-z]+)-Az') { return $Matches[1] }
    return 'Other'
}

# ── Output directories ────────────────────────────────────────────────────────
$DataDir    = Join-Path $OutputDir 'public\data'
$ModulesDir = Join-Path $DataDir 'modules'
New-Item -ItemType Directory -Force -Path $ModulesDir | Out-Null

# ── Discover Az modules ───────────────────────────────────────────────────────
Write-Host "Discovering installed Az modules..." -ForegroundColor Cyan
$azModules = Get-Module -Name 'Az.*' -ListAvailable |
    Sort-Object Name, Version -Descending |
    Group-Object Name | ForEach-Object { $_.Group | Select-Object -First 1 }

if (-not $azModules) {
    Write-Error "No Az.* modules found. Install the Az module first: Install-Module Az"
    exit 1
}

Write-Host "Found $($azModules.Count) Az modules" -ForegroundColor Green

# ── Try to get overall Az version ────────────────────────────────────────────
$azVersion = '0.0.0'
$azMeta = Get-Module -Name 'Az' -ListAvailable | Sort-Object Version -Descending | Select-Object -First 1
if ($azMeta) { $azVersion = $azMeta.Version.ToString() }
else {
    $azAccountsMod = $azModules | Where-Object { $_.Name -eq 'Az.Accounts' } | Select-Object -First 1
    if ($azAccountsMod) { $azVersion = $azAccountsMod.Version.ToString() }
}

$manifestEntries = [System.Collections.Generic.List[hashtable]]::new()
$descriptions    = [ordered]@{}
$skippedCount    = 0

foreach ($mod in $azModules) {
    $moduleName = $mod.Name
    $modVersion = $mod.Version.ToString()
    $category   = Get-Category $moduleName

    Write-Host "  Processing $moduleName $modVersion..." -NoNewline

    # Import module to ensure cmdlets are available
    try {
        Import-Module $moduleName -ErrorAction SilentlyContinue -WarningAction SilentlyContinue
    } catch {}

    $cmdlets = Get-Command -Module $moduleName -CommandType Cmdlet, Function |
               Where-Object { $_.Name -match '^[A-Za-z]+-Az' } |
               Sort-Object Name

    if (-not $cmdlets) {
        Write-Host " (no Az cmdlets found)" -ForegroundColor Yellow
        $skippedCount++
        continue
    }

    $moduleCmdlets = [ordered]@{}

    foreach ($cmd in $cmdlets) {
        $cname = $cmd.Name
        $verb  = Get-VerbFromName $cname

        # Get synopsis
        $synopsis = ''
        try {
            $help = Get-Help $cname -ErrorAction SilentlyContinue
            if ($help -and $help.Synopsis) {
                $synopsis = ($help.Synopsis -replace '\r?\n', ' ').Trim()
                # Remove trailing module path noise
                $synopsis = $synopsis -replace '\s*\[.*?\]$', ''
            }
        } catch {}

        # Get syntax (first variant)
        $syntaxStr = ''
        try {
            $help2 = Get-Help $cname -Full -ErrorAction SilentlyContinue
            if ($help2 -and $help2.syntax -and $help2.syntax.syntaxItem) {
                $first = $help2.syntax.syntaxItem | Select-Object -First 1
                $params = @()
                foreach ($p in $first.parameter) {
                    $req   = $p.required -eq 'true'
                    $ptype = if ($p.parameterValue) { " <$($p.parameterValue)>" } else { '' }
                    $pstr  = "-$($p.name)$ptype"
                    $params += if ($req) { "[$pstr]" } else { "[-$($p.name)$ptype]" }
                }
                $syntaxStr = "$cname " + ($params -join ' ')
            }
        } catch {}

        # Get examples
        $examples = @()
        try {
            $help3 = Get-Help $cname -Examples -ErrorAction SilentlyContinue
            if ($help3 -and $help3.examples -and $help3.examples.example) {
                foreach ($ex in ($help3.examples.example | Select-Object -First 3)) {
                    $code = ($ex.code -replace '\r?\n', "`n").Trim()
                    if ($code) { $examples += $code }
                }
            }
        } catch {}

        # Add to manifest
        $manifestEntries.Add(@{
            n = $cname
            v = $verb
            m = $moduleName
            c = $category
            e = ($examples.Count -gt 0)
        })

        if ($synopsis) { $descriptions[$cname] = $synopsis }

        $moduleCmdlets[$cname] = @{
            syntax   = $syntaxStr
            examples = $examples
        }
    }

    # Write per-module JSON
    $modOut = @{
        module  = $moduleName
        version = $modVersion
        cmdlets = $moduleCmdlets
    }
    $modFile = Join-Path $ModulesDir "$moduleName.json"
    $modOut | ConvertTo-Json -Depth 5 -Compress | Set-Content $modFile -Encoding UTF8
    Write-Host " $($cmdlets.Count) cmdlets" -ForegroundColor Green
}

Write-Host ""
Write-Host "Total cmdlets: $($manifestEntries.Count)" -ForegroundColor Cyan

# ── Write manifest.json ───────────────────────────────────────────────────────
$manifest = @{ v = $azVersion; d = $manifestEntries.ToArray() }
$manifest | ConvertTo-Json -Depth 4 -Compress | Set-Content (Join-Path $DataDir 'manifest.json') -Encoding UTF8
Write-Host "Wrote manifest.json ($($manifestEntries.Count) entries)" -ForegroundColor Green

# ── Write descriptions.json ───────────────────────────────────────────────────
$descriptions | ConvertTo-Json -Depth 2 | Set-Content (Join-Path $DataDir 'descriptions.json') -Encoding UTF8
Write-Host "Wrote descriptions.json ($($descriptions.Count) entries)" -ForegroundColor Green

Write-Host ""
Write-Host "Done! Data written to: $DataDir" -ForegroundColor Green
