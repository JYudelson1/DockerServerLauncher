import React, { useState, useEffect } from 'react';

function LaunchForm({ onLaunch }) {
  const [count, setCount] = useState(8);
  const [keyName, setKeyName] = useState('');
  const [name, setName] = useState('');
  const [keys, setKeys] = useState([]);
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    // Fetch available keys on mount
    fetch('http://localhost:5001/api/keys')
      .then(res => res.json())
      .then(data => {
        setKeys(data.keys);
        setKeyName(data.default || (data.keys.length > 0 ? data.keys[0].name : ''));
      })
      .catch(err => console.error('Failed to fetch keys:', err));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLaunching(true);

    try {
      const response = await fetch('http://localhost:5001/api/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count, key_name: keyName, name })
      });

      if (response.ok) {
        setName('');
        onLaunch();
      }
    } catch (error) {
      console.error('Launch failed:', error);
    } finally {
      setLaunching(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="launch-form">
      <h2>Launch New Deployment</h2>
      
      <label>
        Cluster Name (optional):
        <input 
          type="text" 
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="my-cluster"
        />
      </label>

      <label>
        Instance Count:
        <input 
          type="number" 
          value={count}
          onChange={(e) => setCount(parseInt(e.target.value))}
          min="2"
          max="20"
        />
      </label>

      <label>
        SSH Key:
        <select value={keyName} onChange={(e) => setKeyName(e.target.value)}>
          {keys.map(key => (
            <option key={key.name} value={key.name}>
              {key.name}
            </option>
          ))}
        </select>
      </label>

      <button type="submit" disabled={launching || !keyName}>
        {launching ? 'Launching...' : 'Launch Deployment'}
      </button>
    </form>
  );
}

export default LaunchForm;