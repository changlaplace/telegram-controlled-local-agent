param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "restart")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".agent_runtime"
$StatusPath = Join-Path $RuntimeDir "status.json"
$LaunchPath = Join-Path $RuntimeDir "launcher.json"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonwPath = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Write-JsonFile([string]$Path, [object]$Value) {
    $TempPath = "$Path.tmp"
    $Value | ConvertTo-Json | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-Item -LiteralPath $TempPath -Destination $Path -Force
}

function Get-ProcessInfo([int]$ProcessId) {
    return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Get-ProcessIdValue($ProcessInfo) {
    if ($null -eq $ProcessInfo) {
        return $null
    }
    if ($null -ne $ProcessInfo.ProcessId) {
        return [int]$ProcessInfo.ProcessId
    }
    return [int]$ProcessInfo.Id
}

function Test-ScriptProcess([int]$ProcessId, [string]$ScriptName) {
    $ProcessInfo = Get-ProcessInfo $ProcessId
    $Pattern = '(^|[^A-Za-z0-9_.-])' + [regex]::Escape($ScriptName) + '([^A-Za-z0-9_.-]|$)'
    return $null -ne $ProcessInfo -and $ProcessInfo.CommandLine -match $Pattern
}

function Find-VenvProcess([string]$Executable, [string]$ScriptName) {
    $ResolvedExecutable = [IO.Path]::GetFullPath($Executable)
    $Pattern = '(^|[^A-Za-z0-9_.-])' + [regex]::Escape($ScriptName) + '([^A-Za-z0-9_.-]|$)'
    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ExecutablePath -and
        [IO.Path]::GetFullPath($_.ExecutablePath) -eq $ResolvedExecutable -and
        $_.CommandLine -match $Pattern
    } | Select-Object -First 1
}

function Stop-ProcessTree([int]$ProcessId) {
    $Children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($Child in $Children) {
        Stop-ProcessTree ([int]$Child.ProcessId)
    }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Get-MonitorProcess($Launch) {
    if ($null -ne $Launch -and $Launch.monitor_pid -and (Test-ScriptProcess ([int]$Launch.monitor_pid) "monitor.py")) {
        return Get-ProcessInfo ([int]$Launch.monitor_pid)
    }
    return Find-VenvProcess $PythonwPath "monitor.py"
}

function Get-AgentProcess($Launch, $Status) {
    if ($null -ne $Launch -and $Launch.agent_launcher_pid) {
        $LauncherId = [int]$Launch.agent_launcher_pid
        if ((Test-ScriptProcess $LauncherId "supervisor.py") -or (Test-ScriptProcess $LauncherId "main.py")) {
            return Get-ProcessInfo $LauncherId
        }
    }
    $VenvProcess = Find-VenvProcess $PythonPath "supervisor.py"
    if ($null -ne $VenvProcess) {
        return $VenvProcess
    }
    $VenvProcess = Find-VenvProcess $PythonPath "main.py"
    if ($null -ne $VenvProcess) {
        return $VenvProcess
    }
    if ($null -ne $Status -and $Status.pid -and (Test-ScriptProcess ([int]$Status.pid) "main.py")) {
        return Get-ProcessInfo ([int]$Status.pid)
    }
    return $null
}

function Save-LaunchState($AgentProcess, $MonitorProcess) {
    $State = [ordered]@{
        agent_launcher_pid = Get-ProcessIdValue $AgentProcess
        monitor_pid = Get-ProcessIdValue $MonitorProcess
        updated_at = [DateTime]::UtcNow.ToString("o")
    }
    Write-JsonFile $LaunchPath $State
}

function Set-StoppedStatus {
    $Status = Read-JsonFile $StatusPath
    if ($null -eq $Status) {
        $Status = [ordered]@{}
    }
    $Status.state = "stopped"
    $Status.updated_at = [DateTime]::UtcNow.ToString("o")
    Write-JsonFile $StatusPath $Status
}

function Start-Agent {
    if (-not (Test-Path -LiteralPath $PythonPath) -or -not (Test-Path -LiteralPath $PythonwPath)) {
        throw "Virtual environment not found. Run 'uv sync' in $ProjectRoot first."
    }

    $Launch = Read-JsonFile $LaunchPath
    $Status = Read-JsonFile $StatusPath
    $AgentProcess = Get-AgentProcess $Launch $Status
    if ($null -eq $AgentProcess) {
        $AgentProcess = Start-Process -FilePath $PythonPath `
            -ArgumentList @("-u", "supervisor.py") `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $RuntimeDir "agent.out.log") `
            -RedirectStandardError (Join-Path $RuntimeDir "agent.err.log") `
            -PassThru
        Write-Host "Started agent PID $($AgentProcess.Id)."
    }
    else {
        Write-Host "Agent is already running (PID $($AgentProcess.ProcessId))."
    }

    $MonitorProcess = Get-MonitorProcess $Launch
    if ($null -eq $MonitorProcess) {
        $MonitorProcess = Start-Process -FilePath $PythonwPath `
            -ArgumentList "monitor.py" `
            -WorkingDirectory $ProjectRoot `
            -PassThru
        Write-Host "Opened monitor PID $($MonitorProcess.Id)."
    }

    Save-LaunchState $AgentProcess $MonitorProcess
}

function Stop-Agent {
    $Launch = Read-JsonFile $LaunchPath
    $Status = Read-JsonFile $StatusPath
    $AgentProcess = Get-AgentProcess $Launch $Status

    if ($null -eq $AgentProcess) {
        Write-Host "Agent is not running."
    }
    else {
        $AgentProcessId = [int]$AgentProcess.ProcessId
        Stop-ProcessTree $AgentProcessId
        Write-Host "Stopped agent process tree at PID $AgentProcessId."
    }

    if ($null -ne $Status -and $Status.pid -and (Test-ScriptProcess ([int]$Status.pid) "main.py")) {
        Stop-ProcessTree ([int]$Status.pid)
    }

    $MonitorProcess = Get-MonitorProcess $Launch
    Save-LaunchState $null $MonitorProcess
    Set-StoppedStatus
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
$HashBytes = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($ProjectRoot.ToLowerInvariant()))
$MutexName = "Local\ReportsWagent-" + ([BitConverter]::ToString($HashBytes).Replace("-", "").Substring(0, 16))
$Mutex = New-Object Threading.Mutex($false, $MutexName)
$HasLock = $false

try {
    $HasLock = $Mutex.WaitOne([TimeSpan]::FromSeconds(10))
    if (-not $HasLock) {
        throw "Another agent start or stop operation is still running."
    }

    switch ($Action) {
        "start" { Start-Agent }
        "stop" { Stop-Agent }
        "restart" {
            Stop-Agent
            Start-Agent
        }
    }
}
catch {
    Write-Error $_
    exit 1
}
finally {
    if ($HasLock) {
        $Mutex.ReleaseMutex()
    }
    $Mutex.Dispose()
}
