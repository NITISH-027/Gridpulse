# get_quickml_token.ps1 - exchanges a Zoho grant code for an access token (India DC)
# No credentials are stored in this file or in PowerShell history.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# 1. Safety checks BEFORE asking for credentials
$envPath = Join-Path (Get-Location) ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "FAIL: .env not found in this folder. Run this script from the project folder (where .env lives)."
    exit 1
}
$tracked = $null
try { $tracked = (& git ls-files -- .env 2>$null) } catch { $tracked = $null }
if ($tracked) {
    Write-Host "FAIL: .env is tracked by Git. Stop - do not store credentials until it is removed from tracking (git rm --cached .env) and confirmed ignored."
    exit 1
}

# 2. Prompt for credentials (hidden input; never written to history or disk)
$clientId  = Read-Host "Client ID"
$secSecret = Read-Host "Client Secret" -AsSecureString
$secCode   = Read-Host "Grant Code" -AsSecureString

$bstrSecret = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secSecret)
$bstrCode   = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secCode)
try {
    $clientSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstrSecret)
    $code         = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstrCode)

    $body = @{
        grant_type    = "authorization_code"
        client_id     = $clientId
        client_secret = $clientSecret
        code          = $code
    }
    $clientSecret = $null; $code = $null

    $resp = $null
    try {
        $resp = Invoke-RestMethod -Method Post `
            -Uri "https://accounts.zoho.in/oauth/v2/token" `
            -Body $body -TimeoutSec 20 -UseBasicParsing -ErrorAction Stop
    } catch {
        Write-Host "FAIL: token exchange failed. Check that the grant code has not expired, that client ID/secret are correct, and that the account is on the India DC. Then generate a fresh grant code and retry."
        exit 1
    }
    $body = $null

    if (-not $resp.access_token) {
        Write-Host "FAIL: response did not contain an access token. Nothing was saved."
        exit 1
    }

    # 3. Update .env in place: read as UTF-8, preserve all other content, write atomically as UTF-8 without BOM
    $tempPath = $null
    try {
        $content = [System.IO.File]::ReadAllText($envPath, [System.Text.Encoding]::UTF8)
        $lines = $content -split "`r?`n"
        $lines = $lines | ForEach-Object {
            if ($_ -match "^QUICKML_AUTH_TOKEN=") { "QUICKML_AUTH_TOKEN=$($resp.access_token)" }
            else { $_ }
        }
        if (-not ($lines -match "^QUICKML_AUTH_TOKEN=")) {
            $lines += "QUICKML_AUTH_TOKEN=$($resp.access_token)"
        }
        $hasRefresh = [bool]$resp.refresh_token
        if ($hasRefresh) {
            $found = $false
            $lines = $lines | ForEach-Object {
                if ($_ -match "^QUICKML_REFRESH_TOKEN=") { $found = $true; "QUICKML_REFRESH_TOKEN=$($resp.refresh_token)" }
                else { $_ }
            }
            if (-not $found) { $lines += "QUICKML_REFRESH_TOKEN=$($resp.refresh_token)" }
        }
        $newContent = ($lines -join "`r`n")
        $tempPath = Join-Path (Get-Location) (".env.tmp." + [guid]::NewGuid().ToString("N"))
        [System.IO.File]::WriteAllText($tempPath, $newContent, (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.File]::Replace($tempPath, $envPath, $null)
        $tempPath = $null
    } catch {
        if ($tempPath -and (Test-Path $tempPath)) { Remove-Item $tempPath -Force -ErrorAction SilentlyContinue }
        Write-Host "FAIL: could not confirm the .env update was saved. Check .env yourself before running the smoke test, and retry if needed."
        exit 1
    }

    if ($hasRefresh) {
        Write-Host "OK: access token saved to .env as QUICKML_AUTH_TOKEN (expires in about 1 hour). A refresh token was saved as QUICKML_REFRESH_TOKEN for renewal. No secret values were printed."
    } else {
        Write-Host "OK: access token saved to .env as QUICKML_AUTH_TOKEN (expires in about 1 hour). No refresh token was returned. No secret values were printed."
    }
} finally {
    if ($bstrSecret -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstrSecret) }
    if ($bstrCode   -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstrCode) }
}
