Set-StrictMode -Version Latest

function Get-QuickTunnelUrl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string]$Text
    )

    $matches = [regex]::Matches(
        $Text,
        'https://[a-z0-9-]+\.trycloudflare\.com',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if ($matches.Count -eq 0) {
        return $null
    }

    return $matches[$matches.Count - 1].Value
}

function Get-WorkerOriginUrl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$WorkerSource
    )

    $match = [regex]::Match(
        $WorkerSource,
        'const\s+ORIGIN_URL\s*=\s*"(?<origin>https://[^"]+)"\s*;',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if (-not $match.Success) {
        return $null
    }

    return $match.Groups['origin'].Value
}

function Set-WorkerOriginUrl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$WorkerSource,

        [Parameter(Mandatory)]
        [ValidatePattern('^https://[a-z0-9-]+\.trycloudflare\.com$')]
        [string]$OriginUrl
    )

    $pattern = 'const\s+ORIGIN_URL\s*=\s*"https://[^"]+"\s*;'
    if (-not [regex]::IsMatch($WorkerSource, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
        throw 'Worker không có dòng ORIGIN_URL hợp lệ.'
    }

    return [regex]::Replace(
        $WorkerSource,
        $pattern,
        ('const ORIGIN_URL = "{0}";' -f $OriginUrl),
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
}

Export-ModuleMember -Function Get-QuickTunnelUrl, Get-WorkerOriginUrl, Set-WorkerOriginUrl
