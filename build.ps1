param([ValidateSet('jvm','clr')][string]$Target = 'jvm')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $compilerLock = Get-Content -LiteralPath compiler.lock.json -Raw | ConvertFrom-Json
    [IO.Directory]::CreateDirectory((Join-Path $PSScriptRoot 'target')) | Out-Null
    $compilerPath = Join-Path $PSScriptRoot "target/bhash-compiler-$($compilerLock.version).jar"
    if (-not (Test-Path -LiteralPath $compilerPath)) {
        Invoke-WebRequest -Uri $compilerLock.url -OutFile "$compilerPath.download"
        if ((Get-FileHash -LiteralPath "$compilerPath.download" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $compilerLock.sha256) {
            throw 'Downloaded compiler checksum does not match compiler.lock.json.'
        }
        Move-Item -LiteralPath "$compilerPath.download" -Destination $compilerPath
    }
    if ((Get-FileHash -LiteralPath $compilerPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $compilerLock.sha256) {
        throw 'Compiler checksum does not match compiler.lock.json.'
    }
    & java -Dfile.encoding=UTF-8 tools/GenerateSourceCatalog.java
    if ($LASTEXITCODE -ne 0) { throw 'Bhash source catalog generation failed.' }
    & java -jar $compilerPath deps verify .
    if ($LASTEXITCODE -ne 0) { throw 'Bhash source dependency verification failed.' }
    $output = if ($Target -eq 'jvm') { 'target/crm.jar' } else { 'target/crm-clr' }
    & java -jar $compilerPath compile . --target $Target -o $output
    if ($LASTEXITCODE -ne 0) { throw 'Bhash CRM compilation failed.' }
} finally { Pop-Location }
