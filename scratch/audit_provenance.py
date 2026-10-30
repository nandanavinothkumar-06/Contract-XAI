import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))

from src.legal_sources.acquisition import DEFAULT_APPROVED_HOSTS

sources = [
    'IN_ACT_1872_09',
    'IN_ACT_2023_22',
    'IN_ACT_2000_21',
    'IN_ACT_1963_47',
    'IN_ACT_1996_26',
    'IN_ACT_2023_47'
]

base_art = "data/legal_sources/reference_artifacts"

print("=== PROVENANCE AUDIT ACROSS ALL 6 STATUTORY REFERENCE ARTIFACTS ===\n")
print(f"Approved Hosts Configured: {DEFAULT_APPROVED_HOSTS}\n")

for sid in sources:
    sdir = os.path.join(base_art, sid)
    print(f"--------------------------------------------------")
    print(f"Source: {sid}")
    if not os.path.exists(sdir):
        print("  DIRECTORY NOT FOUND")
        continue
    subdirs = sorted(os.listdir(sdir))
    # Check the primary or latest publication directory
    # Note: for Task 041 sources, check latest v20261017092501 or primary
    print(f"  All subdirs found: {subdirs}")
    latest_sub = subdirs[-1]
    print(f"  Evaluating Subdirectory: {latest_sub}")
    
    meta_path = os.path.join(sdir, latest_sub, "artifact_metadata.json")
    acq_path = os.path.join(sdir, latest_sub, "acquisition_record.json")
    pdf_path = os.path.join(sdir, latest_sub, "original.pdf")
    
    meta = json.load(open(meta_path, encoding='utf-8')) if os.path.exists(meta_path) else {}
    acq = json.load(open(acq_path, encoding='utf-8')) if os.path.exists(acq_path) else {}
    
    print(f"  Issuing Authority Claimed: {meta.get('issuing_authority')}")
    print(f"  Claimed URL:              {meta.get('source_url')}")
    print(f"  Publication Title:        {meta.get('publication_title')}")
    print(f"  Publication Date:         {meta.get('publication_date')}")
    print(f"  Publication Number:       {meta.get('publication_number')}")
    print(f"  Acquisition Timestamp:    {meta.get('acquisition_timestamp')}")
    print(f"  Acquisition Method:       {acq.get('method')}")
    print(f"  Acquisition Status:       {meta.get('acquisition_status')}")
    print(f"  Stored SHA-256 (meta):    {meta.get('sha256')}")
    print(f"  Stored SHA-256 (acq):     {acq.get('sha256')}")
    print(f"  Reviewer Notes:           {meta.get('verification_notes')}")
