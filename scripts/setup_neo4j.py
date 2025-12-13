#!/usr/bin/env python3
"""Setup Neo4j enhancements for Smart City Semantic Search."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.ingestion.neo4j_enhancer import enhance_neo4j_data


async def main():
    """Enhance Neo4j nodes with descriptions and embeddings."""
    print("Enhancing Neo4j nodes...")

    try:
        result = await enhance_neo4j_data()
        print("\nEnhancement Results:")
        print(f"Enhanced: {result.get('enhanced', 0)} nodes")
        print(f"Skipped: {result.get('skipped', 0)} nodes")
        print(f"Labels processed: {result.get('labels_processed', 0)}")
        print("\nNeo4j enhancement complete!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
