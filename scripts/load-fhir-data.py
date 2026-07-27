#!/usr/bin/env python3
"""
Load Synthea FHIR JSON bundles into HAPI FHIR server
Uploads patient data from synthea/output/fhir/ to local HAPI FHIR
"""

import json
import requests
import sys
from pathlib import Path
from typing import Optional
import time

# Configuration
FHIR_BASE_URL = "http://localhost:8090/fhir"
SYNTHEA_OUTPUT_DIR = Path.home() / "source" / "repos" / "SmartHandoff" / "synthea" / "output" / "fhir"
BATCH_SIZE = 10  # Upload in batches to avoid overwhelming the server


def check_fhir_server() -> bool:
    """Check if HAPI FHIR server is running"""
    try:
        response = requests.get(f"{FHIR_BASE_URL}/metadata", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def upload_bundle(bundle_file: Path) -> tuple[bool, Optional[str]]:
    """Upload a FHIR bundle to the server"""
    try:
        with open(bundle_file, 'r', encoding='utf-8') as f:
            bundle_data = json.load(f)
        
        # Use transaction bundle for atomic upload
        headers = {
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        }
        
        response = requests.post(
            FHIR_BASE_URL,
            json=bundle_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            return True, None
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
            
    except Exception as e:
        return False, str(e)


def main():
    print("\n" + "=" * 80)
    print("FHIR Data Loader - Synthea to HAPI FHIR")
    print("=" * 80 + "\n")
    
    # Check FHIR server
    print("Checking HAPI FHIR server connection...")
    if not check_fhir_server():
        print("❌ ERROR: Cannot connect to HAPI FHIR server at", FHIR_BASE_URL)
        print("Please run: .\\scripts\\setup-fhir-server.ps1")
        sys.exit(1)
    print("✓ HAPI FHIR server is running\n")
    
    # Check Synthea output directory
    if not SYNTHEA_OUTPUT_DIR.exists():
        print("❌ ERROR: Synthea output directory not found:", SYNTHEA_OUTPUT_DIR)
        print("Please run: .\\scripts\\generate-synthea-data.ps1")
        sys.exit(1)
    
    # Find all JSON bundle files
    bundle_files = list(SYNTHEA_OUTPUT_DIR.glob("*.json"))
    if not bundle_files:
        print("❌ ERROR: No FHIR JSON files found in:", SYNTHEA_OUTPUT_DIR)
        sys.exit(1)
    
    print(f"Found {len(bundle_files)} FHIR bundle files\n")
    print("=" * 80)
    print("Starting upload...\n")
    
    successful = 0
    failed = 0
    
    for idx, bundle_file in enumerate(bundle_files, 1):
        print(f"[{idx}/{len(bundle_files)}] Uploading {bundle_file.name}...", end=" ")
        
        success, error = upload_bundle(bundle_file)
        
        if success:
            print("✓")
            successful += 1
        else:
            print(f"✗ {error}")
            failed += 1
        
        # Small delay to avoid overwhelming the server
        if idx % BATCH_SIZE == 0:
            time.sleep(1)
    
    print("\n" + "=" * 80)
    print("Upload Complete")
    print("=" * 80)
    print(f"✓ Successful: {successful}")
    if failed > 0:
        print(f"✗ Failed: {failed}")
    print(f"\nTotal uploaded: {successful} patient bundles")
    print("\n" + "=" * 80)
    print("HAPI FHIR Server Access")
    print("=" * 80)
    print(f"Base URL:        {FHIR_BASE_URL}")
    print(f"Web UI:          http://localhost:8090")
    print(f"Search Patients: {FHIR_BASE_URL}/Patient")
    print(f"Patient Count:   {FHIR_BASE_URL}/Patient?_summary=count")
    print("\nExample queries:")
    print("  GET /Patient?name=Smith")
    print("  GET /Patient/123")
    print("  GET /Patient/123/MedicationStatement")
    print("=" * 80 + "\n")
    
    if failed == 0:
        print("Next step: Configure SmartHandoff backend with FHIR_BASE_URL")
        print("Run: .\\scripts\\configure-backend-fhir.ps1\n")
    else:
        print(f"WARNING: {failed} bundles failed to upload")
        print("Check HAPI FHIR logs: docker logs hapi-fhir\n")


if __name__ == "__main__":
    main()
