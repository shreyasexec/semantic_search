#!/usr/bin/env python3
"""Setup Milvus collections for Smart City Semantic Search."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.ingestion.milvus_loader import setup_milvus


async def main():
    """Setup Milvus collections and partitions."""
    print("Setting up Milvus collections...")

    # Default tenant IDs
    tenant_ids = ["tenant_001", "tenant_002", "tenant_003", "tenant_004"]

    try:
        result = await setup_milvus(tenant_ids)
        print("\nSetup Results:")
        print(f"Collections: {result['collections']}")
        if 'partitions' in result:
            print(f"Partitions: {result['partitions']}")
        print("\nMilvus setup complete!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
