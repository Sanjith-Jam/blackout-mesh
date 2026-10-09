import React, { useState, useEffect } from 'react';

const App: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<string>('Connecting...');

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setBackendStatus(data.status === 'ok' ? 'Connected' : 'Error'))
      .catch(() => setBackendStatus('Disconnected'));
  }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <header>
        <h1>PriorityGrid Control Console</h1>
        <p>
          Status: <strong>{backendStatus}</strong>
        </p>
      </header>
      <main style={{ marginTop: '2rem' }}>
        <section>
          <h2>System Overview</h2>
          <p>Frontend initialized according to blueprint plans.</p>
        </section>
      </main>
    </div>
  );
};

export default App;
