# Quick Start - Run this after you have all notification credentials.
# This wizard never displays or stores credential values.

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmartHandoff Notification Setup" -ForegroundColor Cyan
Write-Host "Quick Start Wizard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Before we begin, make sure you have:" -ForegroundColor Yellow
Write-Host ""
Write-Host "From Twilio:" -ForegroundColor Cyan
Write-Host "  - Account SID" -ForegroundColor Green
Write-Host "  - Auth Token" -ForegroundColor Green
Write-Host "  - Verify Service SID (starts with VA...)" -ForegroundColor Yellow
Write-Host "  - Phone Number (format: +15551234567)" -ForegroundColor Yellow
Write-Host ""
Write-Host "From SendGrid:" -ForegroundColor Cyan
Write-Host "  - API Key (starts with SG.)" -ForegroundColor Yellow
Write-Host "  - Verified sender email" -ForegroundColor Yellow
Write-Host ""

$ready = Read-Host "Do you have all items ready? (y/N)"

if ($ready -notin @("y", "Y")) {
    Write-Host ""
    Write-Host "Quick links:" -ForegroundColor Yellow
    Write-Host "  - Buy Twilio Phone: https://console.twilio.com/us1/develop/phone-numbers/manage/search" -ForegroundColor Gray
    Write-Host "  - Create Verify Service: https://console.twilio.com/us1/develop/verify/services" -ForegroundColor Gray
    Write-Host "  - SendGrid Signup: https://signup.sendgrid.com/" -ForegroundColor Gray
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
.\setup-notifications-complete.ps1 -ProjectId "smarthandoff"
