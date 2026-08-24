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
  const [retryTick, setRetryTick] = useState(0);

  const isInstallPath = location.pathname === '/install';
  const allowReinstall = new URLSearchParams(location.search).get('reinstall') === '1';

  useEffect(() => {
    let cancelled = false;
    setError(false);
    setStatus(null);
    fetchSetupStatus({ force: true })
      .then((data) => {
        if (!cancelled) {
          setError(false);
          setStatus(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setStatus(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search, retryTick]);

  if (error) {
    return (
      <div className="app-surface flex min-h-screen items-center justify-center p-8">
        <div className="w-full max-w-md space-y-3 rounded-lg border bg-background p-6 text-center">
          <p className="font-medium">Cannot reach the server</p>
          <p className="text-sm text-muted-foreground">
            The app loaded, but the API did not respond. Check that the backend
            container is running, then try again.
          </p>
          <button
            type="button"
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
            onClick={() => setRetryTick((n) => n + 1)}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

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

  return children;
};

export default SetupGate;
