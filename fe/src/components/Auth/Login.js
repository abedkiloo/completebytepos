import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';

import { authAPI } from '../../services/api';
import { sessionIdleExpiredMessage } from '../../config/sessionConfig';
import { markSessionActivity } from '../../utils/sessionIdle';
import { clearSessionTeardownFlag } from '../../utils/authSession';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../ui/card';

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [fromInstall, setFromInstall] = useState(false);

  useEffect(() => {
    const state = location.state || {};
    if (state.username) setUsername(state.username);
    if (state.password) setPassword(state.password);
    if (state.fromInstall) setFromInstall(true);

    const params = new URLSearchParams(location.search);
    if (params.get('expired') === 'idle' || sessionStorage.getItem('session_expired_reason') === 'idle') {
      setError(sessionIdleExpiredMessage());
      sessionStorage.removeItem('session_expired_reason');
    }
    clearSessionTeardownFlag();

    let cancelled = false;
    import('../../utils/setupStatus')
      .then(({ fetchSetupStatus }) => fetchSetupStatus())
      .then((status) => {
        if (!cancelled && status.needs_install) {
          navigate('/install', { replace: true });
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setCheckingSetup(false);
      });

    return () => {
      cancelled = true;
    };
  }, [location.state, location.search, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError('');
    setLoading(true);

    try {
      const response = await authAPI.login({ username, password });
      const { user, profile, permissions, access, refresh, enabled_modules } = response.data || {};

      if (!user || !access) {
        throw new Error('Unexpected login response.');
      }

      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
      localStorage.setItem('isAuthenticated', 'true');
      localStorage.setItem('user', JSON.stringify(user));
      if (profile) {
        localStorage.setItem('profile', JSON.stringify(profile));
      }
      if (permissions) {
        localStorage.setItem('permissions', JSON.stringify(permissions));
      }

      const { persistMeResponse } = await import('../../utils/roleAccess');
      persistMeResponse({ user, profile, permissions, enabled_modules });

      try {
        const { storeSettingsAPI } = await import('../../services/api');
        const { cacheStoreSettings } = await import('../../utils/storeSettingsCache');
        const settingsRes = await storeSettingsAPI.get();
        cacheStoreSettings(settingsRes.data);
      } catch {
        /* store settings optional at login */
      }

      markSessionActivity();
      clearSessionTeardownFlag();

      const { purgeStaleRetailCartDrafts } = await import('../../utils/posCartRecovery');
      purgeStaleRetailCartDrafts();

      navigate('/');
    } catch (err) {
      setError(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          err.message ||
          'Login failed. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  if (checkingSetup) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background via-background to-secondary px-4 py-10">
        <Card className="w-full max-w-md shadow-xl">
          <CardContent className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Checking setup…
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background via-background to-secondary px-4 py-10">
      <Card className="w-full max-w-md shadow-xl">
        <CardHeader className="items-center text-center">
          <img src="/logo.svg" alt="CompleteByte POS" className="mb-3 h-12 w-auto" />
          <CardTitle className="text-2xl">Welcome back</CardTitle>
          <CardDescription>
            {fromInstall
              ? 'Installation finished — sign in with your new admin account.'
              : 'Sign in to your store to start a new session.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
            {error && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex flex-col gap-1">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. cashier1"
                autoComplete="username"
                required
                autoFocus
                disabled={loading}
              />
            </div>

            <div className="flex flex-col gap-1">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                  disabled={loading}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground focus:outline-none focus-visible:text-foreground"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              size="lg"
              disabled={loading || !username || !password}
              className="mt-2 w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            First time here?{' '}
            <Link to="/install" className="text-primary underline-offset-2 hover:underline">
              Run setup wizard
            </Link>
            {' · '}
            Trouble signing in? Ask your store owner to reset your password.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
