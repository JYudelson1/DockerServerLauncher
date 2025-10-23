import React, { useState, useEffect } from 'react';

function DeploymentRow({ deployment, onDelete }) {
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState([]);

  const handleConnect = async () => {
    await fetch(`http://localhost:5001/api/connect/${deployment.id}`, {
      method: 'POST'
    });
  };

  const handleOpenLogs = async () => {
    await fetch(`http://localhost:5001/api/deployments/${deployment.id}/logs/open`);
  };

  const handleDelete = async () => {
    if (window.confirm(`Delete deployment ${deployment.name}?`)) {
      await fetch(`http://localhost:5001/api/deployments/${deployment.id}`, {
        method: 'DELETE'
      });
      onDelete();
    }
  };

  const toggleLogs = () => {
    if (!showLogs) {
      // Start streaming logs
      setLogs([]);
      const eventSource = new EventSource(
        `http://localhost:5001/api/deployments/${deployment.id}/logs/stream`
      );
      
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'log') {
          setLogs(prev => [...prev, data.message]);
        } else if (data.type === 'complete') {
          eventSource.close();
        }
      };
      
      eventSource.onerror = () => {
        eventSource.close();
      };
      
      // Store eventSource to close it later
      setShowLogs(eventSource);
    } else {
      // Close the stream
      if (showLogs.close) {
        showLogs.close();
      }
      setShowLogs(false);
    }
  };

  const getStatusClass = (status) => {
    return `status-${status}`;
  };

  return (
    <>
      <tr>
        <td>{deployment.name}</td>
        <td>
          <span className={`status-badge ${getStatusClass(deployment.status)}`}>
            {deployment.status}
          </span>
        </td>
        <td>{deployment.head_ip || 'N/A'}</td>
        <td>{deployment.worker_count}</td>
        <td>{new Date(deployment.created_at).toLocaleString()}</td>
        <td>
          <button 
            onClick={handleConnect}
            disabled={deployment.status !== 'running'}
          >
            Connect to Head
          </button>
          <button onClick={handleOpenLogs} className="secondary">
            View Logs
          </button>
          <button onClick={toggleLogs} className="secondary">
            {showLogs ? 'Hide' : 'Show'} Live Logs
          </button>
          <button 
            onClick={handleDelete}
            disabled={deployment.status === 'terminated'}
            className="danger"
          >
            Delete
          </button>
        </td>
      </tr>
      {showLogs && (
        <tr>
          <td colSpan="6">
            <div className="logs-container">
              {logs.map((log, i) => (
                <div key={i}>{log}</div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default DeploymentRow;