# Generate random secrets for production .env (paste into your local .env file)
Write-Host "Copy these into .env (never commit .env):`n"
Write-Host ("SECRET_KEY=" + [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 })))
Write-Host ("JWT_SECRET=" + [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 })))
Write-Host ""
Write-Host "Also set strong ADMIN_PASSWORD and PLATFORM_ADMIN_PASSWORD (16+ chars)."
Write-Host "Rotate TELEGRAM_BOT_TOKEN and OPS_TELEGRAM_BOT_TOKEN in @BotFather if they were ever committed."
