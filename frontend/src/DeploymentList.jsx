import React, { useState } from 'react';
import DeploymentRow from './DeploymentRow';

function DeploymentList({ deployments, onDelete }) {
  const [clearing, setClearing] = useState(false);

  const handleClearTerminated = async () => {
    const terminatedCount = deployments.filter(d => d.status === 'terminated').length;
    
    if (terminatedCount === 0) {
      alert('No terminated deployments to clear');
      return;
    }
    
    if (!window.confirm(`Clear ${terminatedCount} terminated deployment(s)?`)) {
      return;
    }
    
    setClearing(true);
    try {
      const response = await fetch('http://localhost:5001/api/deployments/clear-terminated', {
        method: 'POST'
      });
      
      if (response.ok) {
        onDelete(); // Refresh the list
      }
    } catch (error) {
      console.error('Failed to clear terminated deployments:', error);
    } finally {
      setClearing(false);
    }
  };

  if (deployments.length === 0) {
    return <div className="no-deployments">No deployments yet</div>;
  }

  const terminatedCount = deployments.filter(d => d.status === 'terminated').length;

  return (
    <div className="deployment-list">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Deployments</h2>
        {terminatedCount > 0 && (
          <button 
            onClick={handleClearTerminated}
            disabled={clearing}
            className="secondary"
          >
            {clearing ? 'Clearing...' : `Clear ${terminatedCount} Terminated`}
          </button>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Head IP</th>
            <th>Workers</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {deployments.map(deployment => (
            <DeploymentRow 
              key={deployment.id}
              deployment={deployment}
              onDelete={onDelete}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default DeploymentList;