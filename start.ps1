param(
    [string]$Jar = (Join-Path $PSScriptRoot 'target/crm.jar'),
    [string]$Database = (Join-Path $PSScriptRoot 'data/crm.db'),
    [int]$Port = 8080
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$Jar = [IO.Path]::GetFullPath($Jar)
$Database = [IO.Path]::GetFullPath($Database)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Database)) | Out-Null
if (-not (Test-Path -LiteralPath $Jar)) {
    throw 'Compile the CRM first; see README.md. Use -Jar for another compiled artifact.'
}
$crmSetupStatus = & java '-Dfile.encoding=UTF-8' -jar $Jar "--db=$Database" '--setup-status=true'
if ($LASTEXITCODE -ne 0) { throw 'Could not check account setup. Database was preserved.' }
if ($crmSetupStatus -notcontains 'SETUP_REQUIRED' -and $crmSetupStatus -notcontains 'SETUP_READY') {
    throw 'Rebuild target/crm.jar to enable setup detection.'
}
if ($crmSetupStatus -contains 'SETUP_REQUIRED') {
    $env:BHASH_CRM_USER = Read-Host 'First owner username (3-64 Latin letters, digits, . _ -)'
    $env:BHASH_CRM_TENANT = Read-Host 'Organization name'
    $crmSecurePassword = Read-Host 'Password (at least 12 characters)' -AsSecureString
    $crmPasswordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($crmSecurePassword)
    try {
        $env:BHASH_CRM_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($crmPasswordPointer)
        & java '-Dfile.encoding=UTF-8' -jar $Jar "--db=$Database" '--bootstrap=true'
        if ($LASTEXITCODE -ne 0) { throw 'Initial account setup failed.' }
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($crmPasswordPointer)
        Remove-Item Env:BHASH_CRM_PASSWORD -ErrorAction SilentlyContinue
        Remove-Item Env:BHASH_CRM_USER -ErrorAction SilentlyContinue
        Remove-Item Env:BHASH_CRM_TENANT -ErrorAction SilentlyContinue
        $crmSecurePassword.Dispose()
    }
}
Write-Host "Open http://localhost:$Port or http://127.0.0.1:$Port"
& java '-Dfile.encoding=UTF-8' '-Dstdout.encoding=UTF-8' '-Dstderr.encoding=UTF-8' -jar $Jar "--db=$Database" "--port=$Port" '--local=true'
exit $LASTEXITCODE
