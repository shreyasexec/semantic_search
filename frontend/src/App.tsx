import React, { useState, useEffect, useRef } from 'react';
import ChatInterface from './components/ChatInterface';
import { useWebSocket } from './hooks/useWebSocket';

const App: React.FC = () => {
  const [tenantId, setTenantId] = useState('tenant_001');

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>Smart City Command Center</h1>
        <div style={styles.tenantSelector}>
          <label style={styles.label}>Tenant: </label>
          <select
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            style={styles.select}
          >
            <option value="tenant_001">Smart City Alpha</option>
            <option value="tenant_002">Safe City Beta</option>
            <option value="tenant_003">City Gamma</option>
            <option value="tenant_004">Metro Delta</option>
          </select>
        </div>
      </header>

      <main style={styles.main}>
        <ChatInterface tenantId={tenantId} />
      </main>

      <footer style={styles.footer}>
        <p>Semantic Search System v1.0</p>
      </footer>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#0f172a',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155',
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#f1f5f9',
  },
  tenantSelector: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  label: {
    color: '#94a3b8',
    fontSize: '14px',
  },
  select: {
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid #475569',
    backgroundColor: '#334155',
    color: '#e2e8f0',
    fontSize: '14px',
    cursor: 'pointer',
  },
  main: {
    flex: 1,
    overflow: 'hidden',
  },
  footer: {
    padding: '12px 24px',
    backgroundColor: '#1e293b',
    borderTop: '1px solid #334155',
    textAlign: 'center',
    color: '#64748b',
    fontSize: '12px',
  },
};

export default App;
