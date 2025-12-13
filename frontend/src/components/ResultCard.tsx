import React, { useState } from 'react';

interface ResultCardProps {
  result: {
    id: string;
    source: string;
    entity_type: string;
    content: string;
    properties?: Record<string, any>;
    score?: number;
    rank?: number;
  };
}

const ResultCard: React.FC<ResultCardProps> = ({ result }) => {
  const [expanded, setExpanded] = useState(false);

  const sourceColor = result.source === 'neo4j' ? '#22c55e' : '#8b5cf6';

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={styles.titleRow}>
          <span style={{ ...styles.sourceTag, backgroundColor: sourceColor }}>
            {result.source}
          </span>
          <span style={styles.entityType}>{result.entity_type}</span>
          <span style={styles.id}>{result.id}</span>
        </div>

        {result.score && (
          <span style={styles.score}>
            {(result.score * 100).toFixed(1)}%
          </span>
        )}
      </div>

      <p style={styles.content}>
        {expanded ? result.content : truncate(result.content, 150)}
      </p>

      {result.content.length > 150 && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={styles.expandButton}
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}

      {result.properties && Object.keys(result.properties).length > 0 && (
        <div style={styles.properties}>
          {Object.entries(result.properties)
            .filter(([key]) => !['embedding', 'description'].includes(key))
            .slice(0, 5)
            .map(([key, value]) => (
              <span key={key} style={styles.property}>
                <span style={styles.propertyKey}>{key}:</span>
                <span style={styles.propertyValue}>
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </span>
              </span>
            ))}
        </div>
      )}
    </div>
  );
};

const truncate = (text: string, length: number): string => {
  if (text.length <= length) return text;
  return text.slice(0, length) + '...';
};

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '12px 16px',
    marginBottom: '8px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  titleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  sourceTag: {
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    color: '#ffffff',
    textTransform: 'uppercase',
  },
  entityType: {
    color: '#94a3b8',
    fontSize: '13px',
  },
  id: {
    color: '#64748b',
    fontSize: '12px',
    fontFamily: 'monospace',
  },
  score: {
    color: '#22c55e',
    fontSize: '13px',
    fontWeight: 600,
  },
  content: {
    color: '#e2e8f0',
    fontSize: '14px',
    lineHeight: 1.5,
    margin: 0,
  },
  expandButton: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    fontSize: '13px',
    cursor: 'pointer',
    padding: '4px 0',
    marginTop: '4px',
  },
  properties: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    marginTop: '12px',
    paddingTop: '12px',
    borderTop: '1px solid #334155',
  },
  property: {
    display: 'flex',
    gap: '4px',
    fontSize: '12px',
  },
  propertyKey: {
    color: '#64748b',
  },
  propertyValue: {
    color: '#94a3b8',
    maxWidth: '150px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
};

export default ResultCard;
