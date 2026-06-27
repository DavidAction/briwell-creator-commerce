param(
    [int]$ApiPort = 8030,
    [int]$DashboardPort = 8070
)

# Stops the Briwell backend (API) and dashboard by killing whatever process is
# listening on their ports. Safe to run even if nothing is running.

$ErrorActionPreference = "SilentlyContinue"
$stopped = 0

foreach ($port in @($ApiPort, $DashboardPort)) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($connection in $connections) {
        $procId = $connection.OwningProcess
        if ($procId) {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            Stop-Process -Id $procId -Force
            Write-Host "Stopped PID $procId ($($proc.ProcessName)) on port $port"
            $stopped++
        }
    }
}

if ($stopped -eq 0) {
    Write-Host "No Briwell server was running on ports $ApiPort or $DashboardPort."
} else {
    Write-Host "Briwell stopped ($stopped process(es))."
}
