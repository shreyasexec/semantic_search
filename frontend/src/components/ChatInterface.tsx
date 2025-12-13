import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import ClarificationCard from './ClarificationCard';
import ResultCard from './ResultCard';
import LoadingIndicator from './LoadingIndicator';
import { sendQuery, sendClarification } from '../services/api';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'clarification' | 'results';
  content: string;
  timestamp: Date;
  metadata?: any;
  clarification?: any;
  results?: any[];
}

interface ChatInterfaceProps {
  tenantId: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ tenantId }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await sendQuery(inputValue, tenantId, conversationId);
      setConversationId(response.conversation_id);

      if (response.response_type === 'clarification') {
        const clarificationMessage: Message = {
          id: Date.now().toString(),
          type: 'clarification',
          content: response.clarification?.question || '',
          timestamp: new Date(),
          clarification: response.clarification,
          metadata: response.metadata,
        };
        setMessages((prev) => [...prev, clarificationMessage]);
      } else {
        const assistantMessage: Message = {
          id: Date.now().toString(),
          type: 'assistant',
          content: response.response,
          timestamp: new Date(),
          metadata: response.metadata,
          results: response.results,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      }
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClarificationResponse = async (response: string) => {
    if (!conversationId) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: response,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const result = await sendClarification(conversationId, response);

      const assistantMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: result.response,
        timestamp: new Date(),
        metadata: result.metadata,
        results: result.results,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.messagesContainer}>
        {messages.length === 0 && (
          <div style={styles.welcomeMessage}>
            <h2>Welcome to Smart City Search</h2>
            <p>Ask questions about assets, incidents, and more.</p>
            <div style={styles.exampleQueries}>
              <p style={styles.examplesTitle}>Try asking:</p>
              <ul>
                <li>"What is the status of cameras on the second floor?"</li>
                <li>"Any incidents created yesterday?"</li>
                <li>"Show sensors connected to NVR-001"</li>
                <li>"How many critical incidents this week?"</li>
              </ul>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id}>
            {message.type === 'clarification' ? (
              <ClarificationCard
                question={message.clarification?.question || message.content}
                options={message.clarification?.options || []}
                onSelect={handleClarificationResponse}
              />
            ) : (
              <MessageBubble
                type={message.type as 'user' | 'assistant'}
                content={message.content}
                timestamp={message.timestamp}
                metadata={message.metadata}
              />
            )}

            {message.results && message.results.length > 0 && (
              <div style={styles.resultsContainer}>
                <p style={styles.resultsTitle}>
                  {message.results.length} result(s) found:
                </p>
                {message.results.slice(0, 5).map((result, index) => (
                  <ResultCard key={index} result={result} />
                ))}
                {message.results.length > 5 && (
                  <p style={styles.moreResults}>
                    ... and {message.results.length - 5} more results
                  </p>
                )}
              </div>
            )}
          </div>
        ))}

        {isLoading && <LoadingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} style={styles.inputContainer}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ask about assets, incidents, or search for information..."
          style={styles.input}
          disabled={isLoading}
        />
        <button
          type="submit"
          style={styles.sendButton}
          disabled={isLoading || !inputValue.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
  messagesContainer: {
    flex: 1,
    overflow: 'auto',
    padding: '20px',
  },
  welcomeMessage: {
    textAlign: 'center',
    padding: '40px 20px',
    color: '#94a3b8',
  },
  exampleQueries: {
    marginTop: '24px',
    textAlign: 'left',
    maxWidth: '400px',
    margin: '24px auto 0',
  },
  examplesTitle: {
    color: '#64748b',
    marginBottom: '12px',
  },
  resultsContainer: {
    marginLeft: '48px',
    marginTop: '12px',
    marginBottom: '20px',
  },
  resultsTitle: {
    color: '#64748b',
    fontSize: '13px',
    marginBottom: '12px',
  },
  moreResults: {
    color: '#64748b',
    fontSize: '13px',
    marginTop: '12px',
    textAlign: 'center',
  },
  inputContainer: {
    display: 'flex',
    gap: '12px',
    padding: '16px 20px',
    backgroundColor: '#1e293b',
    borderTop: '1px solid #334155',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    borderRadius: '8px',
    border: '1px solid #475569',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '15px',
    outline: 'none',
  },
  sendButton: {
    padding: '12px 24px',
    borderRadius: '8px',
    border: 'none',
    backgroundColor: '#3b82f6',
    color: '#ffffff',
    fontSize: '15px',
    fontWeight: 500,
    cursor: 'pointer',
  },
};

export default ChatInterface;
