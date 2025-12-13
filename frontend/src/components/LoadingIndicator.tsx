import React from 'react';

const LoadingIndicator: React.FC = () => {
  return (
    <div style={styles.container}>
      <div style={styles.avatar}>AI</div>
      <div style={styles.bubble}>
        <div style={styles.dotsContainer}>
          <span style={{ ...styles.dot, animationDelay: '0ms' }} />
          <span style={{ ...styles.dot, animationDelay: '200ms' }} />
          <span style={{ ...styles.dot, animationDelay: '400ms' }} />
        </div>
      </div>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% {
            transform: scale(0.8);
            opacity: 0.5;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
      `}</style>
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
    backgroundColor: '#334155',
    padding: '16px 20px',
    borderRadius: '12px',
    borderBottomLeftRadius: '4px',
  },
  dotsContainer: {
    display: 'flex',
    gap: '6px',
  },
  dot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#94a3b8',
    animation: 'bounce 1.2s infinite ease-in-out',
  },
};

export default LoadingIndicator;
