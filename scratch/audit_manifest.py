import json

manifest_path = "data/legal_sources/corpus_manifest.json"
manifest = json.load(open(manifest_path, encoding='utf-8'))

print("=== CORPUS MANIFEST INVARIANTS AUDIT ===")
for src in manifest.get("official_sources", []):
    sid = src["source_id"]
    print(f"\nSource ID: {sid} ({src.get('short_name')})")
    print(f"  Verification Status:           {src.get('verification_status')}")
    print(f"  Source Completeness Status:    {src.get('source_completeness_status')}")
    print(f"  Currentness Status:            {src.get('currentness_status')}")
    print(f"  Commencement Status:           {src.get('commencement_status')}")
    print(f"  Authoritative Reference SHA:   {src.get('authoritative_reference_sha256')}")
    print(f"  Source SHA256 (snapshot):      {src.get('source_sha256')}")
    print(f"  Verification Notes:            {src.get('verification_notes')}")
