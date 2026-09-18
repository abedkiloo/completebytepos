import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Eye, EyeOff, Loader2 } from 'lucide-react';

import { authAPI, usersAPI } from '../../services/api';
import { persistMeResponse } from '../../utils/roleAccess';
import { logoutLocally } from '../../utils/authSession';
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

function storedUserId() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    return user?.id || null;
  } catch {
    return null;
  }
}

const ChangePassword = () => {
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError('');

    if (!newPassword || newPassword.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    const userId = storedUserId();
    if (!userId) {
      setError('Your session is missing. Please sign in again.');
      return;
    }

    setLoading(true);
    try {
      await usersAPI.changePassword(userId, newPassword);
      try {
        const me = await authAPI.me();
        persistMeResponse(me.data || {});
      } catch {
        const profile = JSON.parse(localStorage.getItem('profile') || '{}');
        localStorage.setItem(
          'profile',
          JSON.stringify({ ...profile, must_change_password: false })
        );
      }
      navigate('/', { replace: true });
    } catch (err) {
      setError(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          err.message ||
          'Could not save the new password. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    await logoutLocally();
    navigate('/login', { replace: true });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary/40 px-4 py-8">
      <Card className="w-full max-w-md border-border/80 shadow-xl">
        <CardHeader className="space-y-1.5 p-6 pb-4">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
            First sign in
          </p>
          <CardTitle className="text-2xl">Choose your password</CardTitle>
          <CardDescription>
            Your store owner set a temporary password. Pick one only you know
            before you continue — this applies on the web and the app.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6 pt-0">
          <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
            {error ? (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            ) : null}

            <div className="flex flex-col gap-1">
              <Label htmlFor="new-password">New password</Label>
              <div className="relative">
                <Input
                  id="new-password"
                  name="new-password"
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                  required
                  autoFocus
                  disabled={loading}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                name="confirm-password"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                minLength={6}
                required
                disabled={loading}
              />
            </div>

            <Button
              type="submit"
              size="lg"
              disabled={loading || !newPassword || !confirmPassword}
              className="mt-2 w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save password and continue'
              )}
            </Button>
          </form>

          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="mt-6 w-full text-center text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            Sign out instead
          </button>
        </CardContent>
      </Card>
    </div>
  );
};

export default ChangePassword;
