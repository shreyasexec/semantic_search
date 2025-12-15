# Smart City Semantic Search

Schema-agnostic semantic search system for Smart City / Safe City platforms using Neo4j Native Vector for assets and Milvus for incidents.

## Architecture

```
User Query -> FastAPI Backend -> LangGraph Orchestrator -> Response
                    |
         +----------+---------+
         |                    |
      Neo4j               Milvus
    (Assets)            (Incidents)
         |                    |
    Real-time            5-min sync
                              |
                           MSSQL
```

## Features

- **Schema-Agnostic**: No hardcoded entity types or properties
- **Multi-Source**: Neo4j for assets (real-time), Milvus for incidents (5-min sync)
- **Intelligent Routing**: LLM-based intent classification and query routing
- **Clarification Flow**: Active RAG pattern for ambiguous queries
- **Hybrid Search**: Vector + structured filters combined with RRF fusion
- **Multi-Tenant**: Partition isolation per tenant

## Tech Stack

- **Backend**: FastAPI, LangGraph, Python 3.11
- **Frontend**: React 18, TypeScript
- **LLM**: Llama 3.1:8b via Ollama
- **Embeddings**: nomic-embed-text (768-dim) via Ollama
- **Graph DB**: Neo4j 5.11+ with Native Vector
- **Vector DB**: Milvus 2.3+
- **Cache**: Redis 7+
- **Source DB**: MSSQL 2019+

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Neo4j instance at 192.168.110.201:7687
- MSSQL instance at 192.168.110.56:1444
- Ollama instance at 192.168.1.120:11434
- uv (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd semantic_search
```

2. Start infrastructure services:
```bash
docker-compose up -d milvus redis
```

3. Start the backend:
```bash
cd backend
uv run semantic
```

4. Start the frontend (in another terminal):
```bash
cd frontend
npm install
npm run dev
```

5. Access the UI at http://localhost:3000

6. Click "Sync Data" button in the UI to trigger initial data ingestion

**Note:** All data ingestion (MSSQL sync and Neo4j asset embeddings) is triggered from the UI. Embeddings are stored in Milvus (not Neo4j) for efficient vector search.

## API Endpoints

### REST API

- `POST /api/query` - Execute semantic search query
- `POST /api/clarify` - Submit clarification response
- `POST /api/voice` - Transcribe voice input
- `GET /api/health` - Health check
- `POST /api/sync/{tenant_id}` - Trigger MSSQL data sync
- `GET /api/schema/{tenant_id}` - Get discovered schema
- `GET /api/ingestion/status/{tenant_id}` - Get ingestion status and last sync time
- `POST /api/ingestion/trigger/{tenant_id}` - Trigger full ingestion (MSSQL + assets)

### WebSocket

- `ws://localhost:8000/ws/chat/{client_id}` - Real-time chat

## Configuration

Environment variables:

```bash
# Neo4j
NEO4J_URI=neo4j://192.168.110.201:7687
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# MSSQL
MSSQL_HOST=192.168.110.56
MSSQL_PORT=1444
MSSQL_DATABASE=default
MSSQL_USER=administrator
MSSQL_PASSWORD=trinity@123

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Ollama
OLLAMA_HOST=192.168.1.120
OLLAMA_PORT=11434

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# App
LOG_LEVEL=INFO
INGESTION_INTERVAL_MINUTES=5
```

## Project Structure

```
smart-city-semantic-search/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes
│   │   ├── core/          # LangGraph workflow & nodes
│   │   ├── ingestion/     # Data pipelines
│   │   ├── models/        # Pydantic models
│   │   └── services/      # Database clients
│   ├── tests/
│   ├── pyproject.toml     # uv project config
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   └── services/      # API client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Query Examples

| Query | Intent | Response |
|-------|--------|----------|
| "What is the camera status on second floor?" | ASSET_STATUS | Camera status list |
| "Show incidents yesterday" | INCIDENT_SEARCH | Incident list |
| "Cameras connected to NVR-001" | RELATIONSHIP | Related cameras |
| "How many critical incidents this week?" | AGGREGATION | Count |
| "Cameras near the incident location" | HYBRID | Cross-referenced results |

## Development

### Backend

```bash
cd backend
uv run semantic
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
uv run pytest
```

## Performance Targets

- Latency: < 10 seconds
- Recall@10: > 85%
- Faithfulness: > 90%

## License

Proprietary
