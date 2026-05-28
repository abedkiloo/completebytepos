import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { PageLoading } from '../page';
import { fetchSetupStatus } from '../../utils/setupStatus';

/**
 * Redirects to /install when the API reports an uninitialized database.
 * Sends users away from /install once setup is complete (unless reinstalling).
 */
const SetupGate = ({ children }) => {
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(false);

  const isInstallPath = location.pathname === '/install';
  const allowReinstall = new URLSearchParams(location.search).get('reinstall') === '1';

  useEffect(() => {
    let cancelled = false;
    fetchSetupStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setStatus({ installed: true, needs_install: false });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search]);

  if (status === null) {
    return (
      <div className="app-surface flex min-h-screen items-center justify-center p-8">
        <div className="w-full max-w-md">
          <PageLoading rows={3} />
        </div>
      </div>
    );
  }

  if (status.needs_install && !isInstallPath) {
    return <Navigate to="/install" replace />;
  }

  if (!status.needs_install && isInstallPath && !allowReinstall) {
    const token = localStorage.getItem('access_token');
    const isAuth = token && localStorage.getItem('isAuthenticated') === 'true';
    return <Navigate to={isAuth ? '/' : '/login'} replace />;
  }

  if (error && isInstallPath) {
    return children;
  }

  return children;
};

export default SetupGate;
