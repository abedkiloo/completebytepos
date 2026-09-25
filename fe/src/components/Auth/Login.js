import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  AlertCircle,
  BarChart3,
  Eye,
  EyeOff,
  Loader2,
  Package,
  ShoppingCart,
  Users,
} from 'lucide-react';

import { authAPI } from '../../services/api';
import { sessionIdleExpiredMessage } from '../../config/sessionConfig';
import { markSessionActivity } from '../../utils/sessionIdle';
import { clearSessionTeardownFlag } from '../../utils/authSession';
import { fetchSetupStatus } from '../../utils/setupStatus';
import { DEFAULT_STORE_NAME, DEFAULT_STORE_TAGLINE } from '../../utils/storeBranding';
import BrandMark from '../Shared/BrandMark';
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
import { cn } from '../../lib/cn';

const LANDING_POINTS = [
  {
    icon: ShoppingCart,
    title: 'A till that keeps up',
    body: 'Find items by name, SKU, or barcode. Cash, card, or pay later — without leaving the sale.',
  },
  {
    icon: Package,
    title: 'Stock you can trust',
    body: 'Purchases, sales, and counts land in one history so the shelf matches the system.',
  },
  {
    icon: Users,
    title: 'Customers and credit',
    body: 'See who bought what, who still owes, and follow up from one customer record.',
  },
  {
    icon: BarChart3,
    title: 'Close the day clearly',
    body: "Today's sales, low stock, and the week's trend on the home screen — not a spreadsheet.",
  },
];

function LandingPanel({ className }) {
  return (
    <div
      data-testid="login-landing"
      className={cn(
        'relative flex flex-col overflow-hidden bg-foreground text-background',
        className
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-primary/25 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-20 left-8 h-64 w-64 rounded-full bg-primary/10 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage:
            'linear-gradient(hsl(var(--background)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--background)) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      <div className="relative z-10 flex h-full flex-col px-8 py-8 lg:px-12 lg:py-10">
        <div className="flex items-center gap-3">
          <BrandMark className="h-14 w-14" />
          <div>
            <span className="block text-sm font-medium tracking-wide text-background/70">
              {DEFAULT_STORE_NAME}
            </span>
            <span className="block text-xs text-background/50">{DEFAULT_STORE_TAGLINE}</span>
          </div>
        </div>

        <div className="mt-10 flex max-w-lg flex-1 flex-col justify-center lg:mt-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Built for Kenyan shops
          </p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight lg:text-4xl">
            Run the counter, the stock, and the close — from one place.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-background/70 lg:text-base">
            Sign in on the right to start a session. {DEFAULT_STORE_NAME} is the till,
            inventory, and daily numbers for stores that need to move fast.
          </p>

          <ul className="mt-8 hidden space-y-4 lg:block">
            {LANDING_POINTS.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/20 text-primary">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-background/65">{body}</p>
                </div>
              </li>
            ))}
          </ul>

          <div
            aria-hidden
            className="mt-10 hidden max-w-sm rounded-xl border border-background/10 bg-background/5 p-4 lg:block"
          >
            <p className="text-xs font-medium uppercase tracking-wider text-background/50">
              A typical afternoon
            </p>
            <div className="mt-3 grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-lg font-semibold tabular-nums">KSh 70k</p>
                <p className="text-[11px] text-background/55">Today's sales</p>
              </div>
              <div>
                <p className="text-lg font-semibold tabular-nums">31</p>
                <p className="text-[11px] text-background/55">Receipts</p>
              </div>
              <div>
                <p className="text-lg font-semibold tabular-nums text-warning">4</p>
                <p className="text-[11px] text-background/55">Low stock</p>
              </div>
            </div>
          </div>
        </div>

        <p className="relative z-10 mt-8 hidden text-xs text-background/45 lg:block">
          Staff accounts are created by your store owner. Ask them if you cannot sign in.
        </p>
      </div>
    </div>
  );
}

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
    fetchSetupStatus()
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
      const { clearPendingTasksPromptDismissed } = await import('../../utils/dailyNotesTaskAccess');
      clearPendingTasksPromptDismissed();

      const { purgeStaleRetailCartDrafts } = await import('../../utils/posCartRecovery');
      purgeStaleRetailCartDrafts();

      navigate(
        profile?.must_change_password || user?.profile?.must_change_password
          ? '/change-password'
          : '/'
      );
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

  return (
    <div className="flex min-h-screen flex-col bg-background lg:flex-row">
      <div className="bg-foreground px-5 py-6 text-background lg:hidden">
        <div className="flex items-center gap-3">
          <BrandMark className="h-12 w-12" />
          <div>
            <span className="block text-sm font-medium text-background/70">{DEFAULT_STORE_NAME}</span>
            <span className="block text-xs text-background/50">{DEFAULT_STORE_TAGLINE}</span>
          </div>
        </div>
        <h1 className="mt-4 text-xl font-semibold leading-snug tracking-tight">
          Run the counter, the stock, and the close — from one place.
        </h1>
        <p className="mt-2 text-sm text-background/65">
          Sign in below to start a session.
        </p>
      </div>
      <LandingPanel className="hidden min-h-screen lg:flex lg:w-[54%]" />

      <div className="flex flex-1 items-center justify-center bg-secondary/40 px-4 py-8 lg:w-[46%] lg:px-10">
        <Card className="w-full max-w-md border-border/80 shadow-xl">
          <CardHeader className="space-y-1.5 p-6 pb-4">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Staff sign in
            </p>
            <CardTitle className="text-2xl">Sign in</CardTitle>
            <CardDescription>
              {fromInstall
                ? 'Installation finished — sign in with your new admin account.'
                : 'Use the username and password your store owner gave you.'}
            </CardDescription>
          </CardHeader>

          <CardContent className="p-6 pt-0">
            {checkingSetup ? (
              <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
                Checking setup…
              </div>
            ) : (
              <>
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
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Login;
