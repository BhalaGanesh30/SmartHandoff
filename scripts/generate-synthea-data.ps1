# Generate Synthea Synthetic Patient Data
# Downloads Synthea and generates test patients

param(
    [int]$PatientCount = 50,
    [string]$State = "Massachusetts",
    [string]$City = "Boston"
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Synthea Patient Data Generator" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if Java is installed
Write-Host "Checking Java installation..." -ForegroundColor Yellow
$javaVersion = java -version 2>&1 | Select-String "version"
if (-not $javaVersion) {
    Write-Host "ERROR: Java is not installed!" -ForegroundColor Red
    Write-Host "Please install Java 11 or higher from: https://adoptium.net/" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Java is installed: $javaVersion" -ForegroundColor Green

# Create synthea directory
$syntheaDir = "$env:USERPROFILE\source\repos\SmartHandoff\synthea"
if (-not (Test-Path $syntheaDir)) {
    Write-Host "`nCreating Synthea directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $syntheaDir | Out-Null
}

Set-Location $syntheaDir

# Download Synthea if not exists
$syntheaJar = "$syntheaDir\synthea-with-dependencies.jar"
if (-not (Test-Path $syntheaJar)) {
    Write-Host "`nDownloading Synthea..." -ForegroundColor Yellow
    Write-Host "This may take a few minutes..." -ForegroundColor Yellow
    
    $syntheaUrl = "https://github.com/synthetichealth/synthea/releases/latest/download/synthea-with-dependencies.jar"
    try {
        Invoke-WebRequest -Uri $syntheaUrl -OutFile $syntheaJar -UseBasicParsing
        Write-Host "✓ Synthea downloaded successfully" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to download Synthea" -ForegroundColor Red
        Write-Host "Please download manually from: https://github.com/synthetichealth/synthea/releases" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "`n✓ Synthea already downloaded" -ForegroundColor Green
}

# Generate patients
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Generating $PatientCount synthetic patients..." -ForegroundColor Cyan
Write-Host "Location: $City, $State" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "This will take several minutes..." -ForegroundColor Yellow
Write-Host "Generating patients with realistic medical histories..." -ForegroundColor Yellow

java -jar $syntheaJar -p $PatientCount -s 12345 --exporter.fhir.export=true --exporter.baseDirectory="$syntheaDir\output" $State $City

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Patient generation complete!" -ForegroundColor Green
    
    $fhirDir = "$syntheaDir\output\fhir"
    if (Test-Path $fhirDir) {
        $patientFiles = Get-ChildItem -Path $fhirDir -Filter "*.json" | Measure-Object
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "Generated Files" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Location: $fhirDir" -ForegroundColor White
        Write-Host "Files: $($patientFiles.Count) FHIR JSON bundles" -ForegroundColor White
        Write-Host "`nEach file contains:" -ForegroundColor Yellow
        Write-Host "  - Patient demographics" -ForegroundColor White
        Write-Host "  - Medical conditions" -ForegroundColor White
        Write-Host "  - Medications" -ForegroundColor White
        Write-Host "  - Observations (vital signs, labs)" -ForegroundColor White
        Write-Host "  - Encounters (hospital visits)" -ForegroundColor White
        Write-Host "  - Procedures" -ForegroundColor White
        Write-Host "  - Care plans" -ForegroundColor White
        Write-Host "`nNext step: Run .\scripts\load-fhir-data.ps1" -ForegroundColor Cyan
        Write-Host "========================================`n" -ForegroundColor Cyan
    } else {
        Write-Host "WARNING: FHIR output directory not found" -ForegroundColor Yellow
    }
} else {
    Write-Host "`nERROR: Patient generation failed" -ForegroundColor Red
    exit 1
}
