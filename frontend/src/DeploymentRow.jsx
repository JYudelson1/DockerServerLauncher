import React, { useState } from 'react';

function DeploymentRow({ deployment, onDelete }) {
  const [copied, setCopied] = useState(false);

  const handleConnect = async () => {
    await fetch(`http://localhost:5001/api/connect/${deployment.id}`, {
      method: 'POST'
    });
  };

  const handleOpenLogs = async () => {
    await fetch(`http://localhost:5001/api/deployments/${deployment.id}/logs/open`);
  };

  const handleRestart = async () => {
    if (!window.confirm(`Restart deployment ${deployment.name}?`)) {
      return;
    }
    await fetch(`http://localhost:5001/api/deployments/${deployment.id}/restart`, {
      method: 'POST'
    });
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete deployment ${deployment.name}?`)) {
      return;
    }
      await fetch(`http://localhost:5001/api/deployments/${deployment.id}`, {
        method: 'DELETE'
      });
      onDelete();
  };

  const handleCopyExport = () => {
    const exportCommand = `export SCALABLE_DOCKER_SERVER_URL=http://${deployment.head_ip}:8080`;
    navigator.clipboard.writeText(exportCommand).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
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
        <td>
          {deployment.head_ip ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              
              <button 
                onClick={handleCopyExport}
                style={{
                  padding: '4px 8px',
                  fontSize: '12px',
                  background: copied ? '#4caf50' : '#007bff',
                  cursor: 'pointer'
                }}
                title="Copy export command"
              >
                {copied ? '✓' : '📋'}
              </button>
              <span>{deployment.head_ip}</span>
            </div>
          ) : 'N/A'}
        </td>
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
          <button onClick={handleRestart} className="danger" disabled={deployment.status !== 'running'}>
            Restart
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
    </>
  );
}

export default DeploymentRow;