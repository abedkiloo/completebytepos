import React, { useState, useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import ToastContainer from './components/Toast/ToastContainer';
import { subscribeToToasts } from './utils/toast';
import { PageLoading } from './components/page';
import { getPersonaFromStorage, isSuperAdminFromStorage } from './utils/navAccess';
import { authAPI } from './services/api';
import { canAccessRoute, persistMeResponse } from './utils/roleAccess';
import { normalizeModuleSettings, readCachedModules } from './utils/moduleCache';
import SetupGate from './components/Installation/SetupGate';
import { fetchSetupStatus } from './utils/setupStatus';
import './App.css';
import './styles/responsive.css';
import './styles/transitions.css';
import './styles/mobile-fixes.css';

const Login = lazy(() => import('./components/Auth/Login'));
const Dashboard = lazy(() => import('./components/Dashboard/Dashboard'));
const POS = lazy(() => import('./components/POS/v2/POSPage'));
const BillingPOS = lazy(() => import('./components/POS/billing/BillingPOSPage'));
const Products = lazy(() => import('./components/Products/Products'));
const Categories = lazy(() => import('./components/Categories/Categories'));
const Sales = lazy(() => import('./components/Sales/Sales'));
const Inventory = lazy(() => import('./components/Inventory/Inventory'));
const Barcodes = lazy(() => import('./components/Barcodes/Barcodes'));
const Reports = lazy(() => import('./components/Reports/Reports'));
const Expenses = lazy(() => import('./components/Expenses/Expenses'));
const Income = lazy(() => import('./components/Income/Income'));
const Accounting = lazy(() => import('./components/Accounting/Accounting'));
const Users = lazy(() => import('./components/Users/Users'));
const Roles = lazy(() => import('./components/Roles/Roles'));
const Customers = lazy(() => import('./components/Customers/Customers'));
const Suppliers = lazy(() => import('./components/Suppliers/Suppliers'));
const NormalSale = lazy(() => import('./components/NormalSale/NormalSale'));
const ModuleSettings = lazy(() => import('./components/ModuleSettings/ModuleSettings'));
const Invoices = lazy(() => import('./components/Invoices/Invoices'));
const Branches = lazy(() => import('./components/Branches/Branches'));
const Installation = lazy(() => import('./components/Installation/Installation'));

const ProtectedRoute = ({ children }) => {
  const location = useLocation();
  const accessToken = localStorage.getItem('access_token');
  const isAuthenticated = accessToken && localStorage.getItem('isAuthenticated') === 'true';
  const [setupChecked, setSetupChecked] = React.useState(false);
  const [needsInstall, setNeedsInstall] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    fetchSetupStatus()
      .then((s) => {
        if (!cancelled) {
          setNeedsInstall(Boolean(s.needs_install));
          setSetupChecked(true);
        }
      })
      .catch(() => {
        if (!cancelled) setSetupChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!setupChecked) {
    return <RouteFallback />;
  }

  if (needsInstall) {
    return <Navigate to="/install" replace />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const persona = getPersonaFromStorage();
  const isSuperAdmin = isSuperAdminFromStorage();
  const moduleSettings = normalizeModuleSettings(readCachedModules());
  if (
    !canAccessRoute(persona, location.pathname, {
      isSuperAdmin,
      moduleSettings,
    })
  ) {
    return <Navigate to="/" replace />;
  }

  return children;
};

function AuthBootstrap({ children }) {
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token || localStorage.getItem('isAuthenticated') !== 'true') return;
    authAPI
      .me()
      .then((res) => persistMeResponse(res.data))
      .catch(() => {});
  }, []);
  return children;
}

function RouteFallback() {
  return (
    <div className="app-surface flex min-h-screen items-center justify-center p-8">
      <div className="w-full max-w-md">
        <PageLoading rows={4} />
      </div>
    </div>
  );
}

function App() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const unsubscribe = subscribeToToasts((newToast) => {
      setToasts((prev) => [...prev, newToast]);
    });
    return () => unsubscribe();
  }, []);

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return (
    <Router>
      <div className="App">
        <AuthBootstrap>
        <ToastContainer toasts={toasts} removeToast={removeToast} />
        <SetupGate>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/install" element={<Installation />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/pos"
              element={
                <ProtectedRoute>
                  <POS />
                </ProtectedRoute>
              }
            />
            <Route
              path="/pos/billing"
              element={
                <ProtectedRoute>
                  <BillingPOS />
                </ProtectedRoute>
              }
            />
            <Route
              path="/products"
              element={
                <ProtectedRoute>
                  <Products />
                </ProtectedRoute>
              }
            />
            <Route
              path="/categories"
              element={
                <ProtectedRoute>
                  <Categories />
                </ProtectedRoute>
              }
            />
            <Route
              path="/sales"
              element={
                <ProtectedRoute>
                  <Sales />
                </ProtectedRoute>
              }
            />
            <Route
              path="/inventory"
              element={
                <ProtectedRoute>
                  <Inventory />
                </ProtectedRoute>
              }
            />
            <Route
              path="/barcodes"
              element={
                <ProtectedRoute>
                  <Barcodes />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <Reports />
                </ProtectedRoute>
              }
            />
            <Route
              path="/expenses"
              element={
                <ProtectedRoute>
                  <Expenses />
                </ProtectedRoute>
              }
            />
            <Route
              path="/accounting"
              element={
                <ProtectedRoute>
                  <Accounting />
                </ProtectedRoute>
              }
            />
            <Route
              path="/income"
              element={
                <ProtectedRoute>
                  <Income />
                </ProtectedRoute>
              }
            />
            <Route
              path="/users"
              element={
                <ProtectedRoute>
                  <Users />
                </ProtectedRoute>
              }
            />
            <Route
              path="/roles"
              element={
                <ProtectedRoute>
                  <Roles />
                </ProtectedRoute>
              }
            />
            <Route
              path="/customers"
              element={
                <ProtectedRoute>
                  <Customers />
                </ProtectedRoute>
              }
            />
            <Route
              path="/suppliers"
              element={
                <ProtectedRoute>
                  <Suppliers />
                </ProtectedRoute>
              }
            />
            <Route
              path="/normal-sale"
              element={
                <ProtectedRoute>
                  <NormalSale />
                </ProtectedRoute>
              }
            />
            <Route
              path="/module-settings"
              element={
                <ProtectedRoute>
                  <ModuleSettings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/invoices"
              element={
                <ProtectedRoute>
                  <Invoices />
                </ProtectedRoute>
              }
            />
            <Route
              path="/branches"
              element={
                <ProtectedRoute>
                  <Branches />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
        </SetupGate>
        </AuthBootstrap>
      </div>
    </Router>
  );
}

export default App;
