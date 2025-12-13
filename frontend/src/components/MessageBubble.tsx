import React from 'react';

interface MessageBubbleProps {
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  metadata?: {
    intent?: string;
    query_strategy?: string;
    execution_time_ms?: number;
  };
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  type,
  content,
  timestamp,
  metadata,
}) => {
  const isUser = type === 'user';

  return (
    <div style={{ ...styles.container, justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && (
        <div style={styles.avatar}>AI</div>
      )}

      <div style={{ ...styles.bubble, ...(isUser ? styles.userBubble : styles.assistantBubble) }}>
        <p style={styles.content}>{content}</p>

        <div style={styles.footer}>
          <span style={styles.timestamp}>
            {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>

          {metadata && !isUser && (
            <span style={styles.metadata}>
              {metadata.intent && (
                <span style={styles.metaItem}>{metadata.intent}</span>
              )}
              {metadata.execution_time_ms && (
                <span style={styles.metaItem}>{metadata.execution_time_ms}ms</span>
              )}
            </span>
          )}
        </div>
      </div>

      {isUser && (
        <div style={{ ...styles.avatar, backgroundColor: '#3b82f6' }}>You</div>
      )}
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
    marginBottom: '16px',
  },
  avatar: {
    width: '36px',
    height: '36px',
    borderRadius: '50%',
    backgroundColor: '#475569',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: 600,
    color: '#e2e8f0',
    flexShrink: 0,
  },
  bubble: {
    maxWidth: '70%',
    padding: '12px 16px',
    borderRadius: '12px',
  },
  userBubble: {
    backgroundColor: '#3b82f6',
    color: '#ffffff',
    borderBottomRightRadius: '4px',
  },
  assistantBubble: {
    backgroundColor: '#334155',
    color: '#e2e8f0',
    borderBottomLeftRadius: '4px',
  },
  content: {
    margin: 0,
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: '8px',
    gap: '12px',
  },
  timestamp: {
    fontSize: '11px',
    opacity: 0.7,
  },
  metadata: {
    display: 'flex',
    gap: '8px',
    fontSize: '11px',
    opacity: 0.7,
  },
  metaItem: {
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    padding: '2px 6px',
    borderRadius: '4px',
  },
};

export default MessageBubble;
