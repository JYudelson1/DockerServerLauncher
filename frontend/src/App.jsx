import React, { useState, useEffect } from 'react';
import LaunchForm from './LaunchForm';
import DeploymentList from './DeploymentList';

function App() {
  const [deployments, setDeployments] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDeployments = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/deployments');
      const data = await response.json();
      setDeployments(data.deployments);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch deployments:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeployments();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchDeployments, 5001);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="App">
      <h1>AWS Deployment Manager</h1>
      <LaunchForm onLaunch={fetchDeployments} />
      {loading ? (
        <div>Loading deployments...</div>
      ) : (
        <DeploymentList 
          deployments={deployments} 
          onDelete={fetchDeployments}
        />
      )}
    </div>
  );
}

export default App;