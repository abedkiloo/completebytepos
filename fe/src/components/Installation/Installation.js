import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, Loader2, LogIn, Rocket, Sparkles, XCircle } from 'lucide-react';
import { authAPI, installAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/cn';
import { MODULE_PRESETS, DEFAULT_MODULE_PRESET } from '../../utils/modulePresets';
import { clearSetupStatusCache, markSetupInstalled } from '../../utils/setupStatus';
import { persistMeResponse } from '../../utils/roleAccess';

const Installation = () => {
  const navigate = useNavigate();
  const [installing, setInstalling] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const [steps, setSteps] = useState([]);
  const [modulePreset, setModulePreset] = useState(DEFAULT_MODULE_PRESET);
  const [includeTestData, setIncludeTestData] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [credentials, setCredentials] = useState(null);

  const primaryCreds = credentials?.primary || credentials;
  const allUsers = credentials?.users || (primaryCreds ? [primaryCreds] : []);

  const handleInstall = async () => {
    if (installing) return;
    if (
      !window.confirm(
        'This will reset the database and run a fresh install. All existing data will be lost. Continue?'
      )
    ) {
      return;
    }

    setInstalling(true);
    setSteps([]);
    setCompleted(false);
    clearSetupStatusCache();

    try {
      const response = await installAPI.freshInstall({
        include_test_data: includeTestData,
        skip_db_delete: false,
        module_preset: modulePreset,
      });

      if (response.data.success) {
        setSteps(response.data.steps || []);
        setCredentials(response.data.credentials);
        markSetupInstalled();
        setCompleted(true);
        toast.success('Installation complete');
      } else {
        throw new Error(response.data.error || 'Installation failed');
      }
    } catch (error) {
      toast.error(error.response?.data?.error || error.message || 'Installation failed');
      setSteps(error.response?.data?.steps || []);
    } finally {
      setInstalling(false);
    }
  };

  const goToLogin = (prefill = true) => {
    if (!prefill || !primaryCreds) {
      navigate('/login');
      return;
    }
    navigate('/login', {
      state: {
        username: primaryCreds.username,
        password: primaryCreds.password,
        fromInstall: true,
      },
    });
  };

  const handleSignInNow = async () => {
    if (!primaryCreds?.username || !primaryCreds?.password) {
      goToLogin(false);
      return;
    }
    setSigningIn(true);
    try {
      const response = await authAPI.login({
        username: primaryCreds.username,
        password: primaryCreds.password,
      });
      const { user, profile, permissions, access, refresh, enabled_modules } =
        response.data || {};

      if (!user || !access) {
        throw new Error('Unexpected login response.');
      }

      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
      localStorage.setItem('isAuthenticated', 'true');
      localStorage.setItem('user', JSON.stringify(user));
      if (profile) localStorage.setItem('profile', JSON.stringify(profile));
      if (permissions) localStorage.setItem('permissions', JSON.stringify(permissions));
      persistMeResponse({ user, profile, permissions, enabled_modules });
      markSetupInstalled();
      toast.success(`Signed in as ${user.username}`);
      navigate('/');
    } catch (err) {
      toast.error(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          'Sign-in failed — use Go to login and try manually.'
      );
      goToLogin(true);
    } finally {
      setSigningIn(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background via-background to-secondary/50 px-4 py-10">
      <Card className="w-full max-w-2xl shadow-xl">
        <CardHeader className="items-center text-center">
          <img src="/logo.svg" alt="" className="mb-2 h-12" />
          <CardTitle className="flex items-center justify-center gap-2 text-2xl">
            <Rocket className="h-7 w-7 text-primary" />
            Set up CompleteByte POS
          </CardTitle>
          <CardDescription>
            Fresh database, roles, and a module preset tuned for your business.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {!completed ? (
            <>
              <div className="space-y-3">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="h-4 w-4 text-primary" />
                  Choose a module preset
                </p>
                <div className="grid gap-2 sm:grid-cols-1">
                  {MODULE_PRESETS.map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      disabled={installing}
                      onClick={() => setModulePreset(opt.id)}
                      className={cn(
                        'rounded-lg border p-3 text-left transition',
                        modulePreset === opt.id
                          ? 'border-primary bg-primary/5 ring-1 ring-primary'
                          : 'hover:border-primary/30'
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{opt.label}</span>
                        {modulePreset === opt.id && (
                          <Badge variant="default">Selected</Badge>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{opt.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={includeTestData}
                  onChange={(e) => setIncludeTestData(e.target.checked)}
                  disabled={installing}
                />
                <span>Include demo test data (not for production)</span>
              </label>

              <Button className="w-full" size="lg" onClick={handleInstall} disabled={installing}>
                {installing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Installing…
                  </>
                ) : (
                  'Run installation'
                )}
              </Button>

              {steps.length > 0 && (
                <ul className="space-y-2 rounded-lg border bg-muted/20 p-3 text-sm">
                  {steps.map((step, i) => (
                    <li key={i} className="flex gap-2">
                      {step.status === 'completed' ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                      ) : step.status === 'error' ? (
                        <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                      ) : (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                      )}
                      <div>
                        <p className="font-medium">{step.name}</p>
                        {step.message && (
                          <p className="text-xs text-muted-foreground">{step.message}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              <p className="text-center text-xs text-muted-foreground">
                Already installed?{' '}
                <Link to="/login" className="text-primary underline-offset-2 hover:underline">
                  Sign in
                </Link>
              </p>
            </>
          ) : (
            <div className="space-y-4">
              <div className="text-center">
                <CheckCircle2 className="mx-auto h-12 w-12 text-success" />
                <p className="mt-2 font-semibold">Ready to sign in</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Change default passwords after your first login.
                </p>
              </div>

              {allUsers.length > 0 && (
                <ul className="rounded-lg border bg-muted/20 p-3 text-sm">
                  {allUsers.map((u) => (
                    <li
                      key={u.username}
                      className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border py-2 last:border-0"
                    >
                      <span className="font-medium">{u.label || u.username}</span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {u.username} / {u.password}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              <Button
                className="w-full"
                size="lg"
                onClick={handleSignInNow}
                disabled={signingIn}
              >
                {signingIn ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <>
                    <LogIn className="h-4 w-4" />
                    Sign in as {primaryCreds?.username || 'admin'}
                  </>
                )}
              </Button>
              <Button className="w-full" variant="outline" onClick={() => goToLogin(true)}>
                Go to login page
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Installation;
