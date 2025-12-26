#!/usr/bin/env python3
"""
Simple test to verify doc_check module works correctly.
"""

import sys
from pathlib import Path

# Test import
try:
    import doc_check
    print("✓ doc_check module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import doc_check: {e}")
    sys.exit(1)

# Test basic functionality
project_dir = Path(".")

try:
    # Check for drift
    has_drift, drift_items, store = doc_check.check_drift_before_finish(project_dir)

    print(f"\nDocumentation drift check results:")
    print(f"  Has drift: {has_drift}")
    print(f"  Drift items found: {len(drift_items)}")

    if drift_items:
        print(f"\nDrift details:")
        for i, drift in enumerate(drift_items, 1):
            print(f"  {i}. [{drift.type}] {drift.item}")
            print(f"     Location: {drift.location}")
    else:
        print("  No drift detected")

    # Test DocDecisionStore
    print(f"\nDecision store:")
    print(f"  Decisions file: {store.decisions_file}")
    print(f"  Existing decisions: {len(store.decisions)}")

    print("\n✓ All basic tests passed")

except Exception as e:
    print(f"\n✗ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
