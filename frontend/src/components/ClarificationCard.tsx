import React, { useState } from 'react';

interface ClarificationOption {
  label: string;
  value: string;
}

interface ClarificationCardProps {
  question: string;
  options: ClarificationOption[];
  onSelect: (value: string) => void;
}

const ClarificationCard: React.FC<ClarificationCardProps> = ({
  question,
  options,
  onSelect,
}) => {
  const [customInput, setCustomInput] = useState('');

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customInput.trim()) {
      onSelect(customInput.trim());
      setCustomInput('');
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.avatar}>?</div>

      <div style={styles.card}>
        <p style={styles.question}>{question}</p>

        {options.length > 0 && (
          <div style={styles.optionsContainer}>
            {options.map((option, index) => (
              <button
                key={index}
                onClick={() => onSelect(option.value)}
                style={styles.optionButton}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleCustomSubmit} style={styles.customInputContainer}>
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            placeholder="Or type your response..."
            style={styles.customInput}
          />
          <button
            type="submit"
            style={styles.submitButton}
            disabled={!customInput.trim()}
          >
            Submit
          </button>
        </form>
      </div>
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
    backgroundColor: '#f59e0b',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '18px',
    fontWeight: 600,
    color: '#ffffff',
    flexShrink: 0,
  },
  card: {
    backgroundColor: '#1e293b',
    border: '1px solid #f59e0b',
    borderRadius: '12px',
    padding: '16px',
    maxWidth: '70%',
  },
  question: {
    margin: '0 0 16px 0',
    color: '#e2e8f0',
    fontSize: '15px',
    lineHeight: 1.5,
  },
  optionsContainer: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    marginBottom: '16px',
  },
  optionButton: {
    padding: '8px 16px',
    borderRadius: '20px',
    border: '1px solid #475569',
    backgroundColor: '#334155',
    color: '#e2e8f0',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  customInputContainer: {
    display: 'flex',
    gap: '8px',
  },
  customInput: {
    flex: 1,
    padding: '10px 14px',
    borderRadius: '8px',
    border: '1px solid #475569',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '14px',
    outline: 'none',
  },
  submitButton: {
    padding: '10px 16px',
    borderRadius: '8px',
    border: 'none',
    backgroundColor: '#f59e0b',
    color: '#ffffff',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
  },
};

export default ClarificationCard;
