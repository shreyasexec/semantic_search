const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface QueryResponse {
  response_type: 'answer' | 'clarification' | 'error';
  response: string;
  clarification?: {
    question: string;
    options: Array<{ label: string; value: string }>;
    allow_free_text: boolean;
  };
  results: Array<{
    id: string;
    source: string;
    entity_type: string;
    content: string;
    properties: Record<string, any>;
    score?: number;
    rank?: number;
  }>;
  metadata: {
    intent: string;
    query_strategy: string;
    execution_time_ms: number;
    neo4j_results_count: number;
    milvus_results_count: number;
    cypher_query?: string;
  };
  conversation_id: string;
}

export async function sendQuery(
  query: string,
  tenantId: string,
  conversationId?: string | null
): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      tenant_id: tenantId,
      conversation_id: conversationId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Query failed');
  }

  return response.json();
}

export async function sendClarification(
  conversationId: string,
  clarificationResponse: string
): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/clarify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      clarification_response: clarificationResponse,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Clarification failed');
  }

  return response.json();
}

export async function checkHealth(): Promise<{
  status: string;
  components: Record<string, string>;
}> {
  const response = await fetch(`${API_BASE_URL}/api/health`);

  if (!response.ok) {
    throw new Error('Health check failed');
  }

  return response.json();
}

export async function transcribeVoice(audioBlob: Blob): Promise<{ text: string }> {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.wav');

  const response = await fetch(`${API_BASE_URL}/api/voice`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Voice transcription failed');
  }

  return response.json();
}
