import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from '../../utils/toast';
import './Installation.css';

// Determine API URL (same logic as api.js)
const getApiBaseUrl = () => {
  const isHttps = window.location.protocol === 'https:';
  const isNgrok = window.location.hostname.includes('ngrok');
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  
  let API_BASE_URL = process.env.REACT_APP_API_URL;
  
  if (!API_BASE_URL) {
    if (window.REACT_APP_API_URL) {
      API_BASE_URL = window.REACT_APP_API_URL;
    } else if (isHttps || isNgrok) {
      const backendNgrokUrl = localStorage.getItem('backend_ngrok_url');
      if (backendNgrokUrl) {
        API_BASE_URL = `${backendNgrokUrl}/api`;
      } else {
        API_BASE_URL = 'http://localhost:8000/api';
      }
    } else if (!isLocalhost) {
      // Server deployment - use same hostname, port 8000
      const protocol = window.location.protocol;
      const hostname = window.location.hostname;
      API_BASE_URL = `${protocol}//${hostname}:8000/api`;
    } else {
      API_BASE_URL = 'http://localhost:8000/api';
    }
  }
  
  return API_BASE_URL;
};

const Installation = () => {
  const navigate = useNavigate();
  const [installing, setInstalling] = useState(false);
  const [steps, setSteps] = useState([]);
  const [includeTestData, setIncludeTestData] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [credentials, setCredentials] = useState(null);

  const API_BASE_URL = getApiBaseUrl();

  const handleInstall = async () => {
    if (installing) return;

    setInstalling(true);
    setSteps([]);
    setCompleted(false);
    setCredentials(null);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/settings/fresh-install/`,
        {
          include_test_data: includeTestData,
          skip_db_delete: false
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data.success) {
        setSteps(response.data.steps || []);
        setCredentials(response.data.credentials);
        setCompleted(true);
        toast.success('Installation completed successfully!');
      } else {
        throw new Error(response.data.error || 'Installation failed');
      }
    } catch (error) {
      console.error('Installation error:', error);
      const errorMessage = error.response?.data?.error || error.message || 'Installation failed';
      toast.error(`Installation failed: ${errorMessage}`);
      setSteps(error.response?.data?.steps || []);
    } finally {
      setInstalling(false);
    }
  };

  const handleLogin = () => {
    navigate('/login');
  };

  const getStepIcon = (status) => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'error':
        return '✗';
      case 'warning':
        return '⚠';
      case 'running':
        return '⟳';
      default:
        return '○';
    }
  };

  const getStepClass = (status) => {
    switch (status) {
      case 'completed':
        return 'step-completed';
      case 'error':
        return 'step-error';
      case 'warning':
        return 'step-warning';
      case 'running':
        return 'step-running';
      default:
        return 'step-pending';
    }
  };

  return (
    <div className="installation-page">
      <div className="installation-container">
        <div className="installation-header">
          <div className="installation-logo">
            <img src="/logo.svg" alt="CompleteByte POS" className="installation-logo-img" />
          </div>
          <h1>🚀 CompleteBytePOS Installation</h1>
          <p>Welcome! Let's set up your POS system from scratch.</p>
        </div>

        {!completed ? (
          <div className="installation-content">
            <div className="installation-info">
              <h2>What will be installed?</h2>
              <ul className="installation-checklist">
                <li>✓ Fresh database with all tables</li>
                <li>✓ Superuser account (admin/admin)</li>
                <li>✓ Permissions and roles system</li>
                <li>✓ All modules and features</li>
                <li>✓ Accounting chart of accounts</li>
                <li>✓ Expense categories</li>
                <li>✓ Default organization and branch</li>
                {includeTestData && (
                  <>
                    <li>✓ 20 test users</li>
                    <li>✓ 100 test customers</li>
                    <li>✓ 1000 test products</li>
                  </>
                )}
              </ul>

              <div className="test-data-option">
                <label>
                  <input
                    type="checkbox"
                    checked={includeTestData}
                    onChange={(e) => setIncludeTestData(e.target.checked)}
                    disabled={installing}
                  />
                  <span>Include test data (recommended for testing)</span>
                </label>
                <small>This will populate the system with sample users, customers, and products</small>
              </div>
            </div>

            <div className="installation-actions">
              <button
                onClick={handleInstall}
                disabled={installing}
                className="btn-install"
              >
                {installing ? (
                  <>
                    <span className="spinner"></span>
                    Installing...
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    Start Installation
                  </>
                )}
              </button>
            </div>

            {steps.length > 0 && (
              <div className="installation-steps">
                <h3>Installation Progress</h3>
                <div className="steps-list">
                  {steps.map((step, index) => (
                    <div key={index} className={`step-item ${getStepClass(step.status)}`}>
                      <span className="step-icon">{getStepIcon(step.status)}</span>
                      <div className="step-content">
                        <div className="step-name">{step.name}</div>
                        {step.message && (
                          <div className="step-message">{step.message}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="installation-complete">
            <div className="success-icon">✅</div>
            <h2>Installation Complete!</h2>
            <p>Your CompleteBytePOS system has been successfully installed.</p>

            {credentials && (
              <div className="credentials-box">
                <h3>Login Credentials</h3>
                <div className="credential-item">
                  <strong>Username:</strong> <code>{credentials.username}</code>
                </div>
                <div className="credential-item">
                  <strong>Password:</strong> <code>{credentials.password}</code>
                </div>
                <div className="credential-warning">
                  ⚠️ <strong>Important:</strong> Please change the default password after first login!
                </div>
              </div>
            )}

            <div className="completion-actions">
              <button onClick={handleLogin} className="btn-login">
                Go to Login
              </button>
            </div>

            {steps.length > 0 && (
              <div className="installation-summary">
                <h3>Installation Summary</h3>
                <div className="steps-list">
                  {steps.map((step, index) => (
                    <div key={index} className={`step-item ${getStepClass(step.status)}`}>
                      <span className="step-icon">{getStepIcon(step.status)}</span>
                      <div className="step-content">
                        <div className="step-name">{step.name}</div>
                        {step.message && (
                          <div className="step-message">{step.message}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Installation;
