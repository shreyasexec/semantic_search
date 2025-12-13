#!/usr/bin/env python3
"""Initial data ingestion for Smart City Semantic Search."""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.ingestion.mssql_extractor import MSSQLIngestion
from app.ingestion.milvus_loader import setup_milvus


async def main(tenant_id: str, full: bool = True):
    """Run initial data ingestion.

    Args:
        tenant_id: Tenant identifier
        full: Whether to run full sync
    """
    print(f"Starting initial ingestion for tenant: {tenant_id}")

    # Setup Milvus collections first
    print("\n1. Setting up Milvus collections...")
    await setup_milvus([tenant_id])

    # Run ingestion
    print("\n2. Running data ingestion...")
    ingestion = MSSQLIngestion()

    try:
        if full:
            result = await ingestion.run_full_sync(tenant_id)
        else:
            from datetime import datetime, timedelta
            last_sync = datetime.now() - timedelta(days=30)
            result = await ingestion.run_incremental_sync(tenant_id, last_sync)

        print("\nIngestion Results:")
        print(f"Records synced: {result.get('synced', 0)}")
        print(f"Chunks created: {result.get('chunks', 0)}")
        print("\nInitial ingestion complete!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initial data ingestion")
    parser.add_argument(
        "--tenant",
        default="tenant_001",
        help="Tenant ID (default: tenant_001)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Run incremental sync instead of full",
    )

    args = parser.parse_args()

    import asyncio
    asyncio.run(main(args.tenant, not args.incremental))
