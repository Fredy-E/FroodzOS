Write-Host "D free: $([math]::Round((Get-PSDrive D).Free / 1GB, 1)) GB"
