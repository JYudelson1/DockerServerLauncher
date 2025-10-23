import React from 'react';
import DeploymentRow from './DeploymentRow';

function DeploymentList({ deployments, onDelete }) {
  if (deployments.length === 0) {
    return <div className="no-deployments">No deployments yet</div>;
  }

  return (
    <div className="deployment-list">
      <h2>Deployments</h2>
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