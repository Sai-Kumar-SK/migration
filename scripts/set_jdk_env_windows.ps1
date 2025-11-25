$ErrorActionPreference = 'Stop'
param(
    [string]$Java8 = 'C:\Program Files\Java\jdk1.8.0',
    [string]$Java11 = 'C:\Program Files\Java\jdk-11',
    [string]$Java17 = 'C:\Program Files\Java\jdk-17',
    [string]$Java21 = 'C:\Program Files\Java\jdk-21'
)

Write-Host "Setting JAVA*_HOME environment variables (User scope)"
if ($Java8)  { [Environment]::SetEnvironmentVariable('JAVA8_HOME',  $Java8,  'User') }
if ($Java11) { [Environment]::SetEnvironmentVariable('JAVA11_HOME', $Java11, 'User') }
if ($Java17) { [Environment]::SetEnvironmentVariable('JAVA17_HOME', $Java17, 'User') }
if ($Java21) { [Environment]::SetEnvironmentVariable('JAVA21_HOME', $Java21, 'User') }

Write-Host "Done. Restart your terminal to pick up changes."