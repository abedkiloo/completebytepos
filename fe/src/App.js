import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import ToastContainer from './components/Toast/ToastContainer';
import { subscribeToToasts } from './utils/toast';
import './App.css';
import './styles/responsive.css';
import './styles/transitions.css';
import './styles/mobile-fixes.css';

// Components
import Login from './components/Auth/Login';
import Dashboard from './components/Dashboard/Dashboard';
import POS from './components/POS/POS';
import Products from './components/Products/Products';
import Categories from './components/Categories/Categories';
import Sales from './components/Sales/Sales';
import Inventory from './components/Inventory/Inventory';
import Barcodes from './components/Barcodes/Barcodes';
import Reports from './components/Reports/Reports';
import Expenses from './components/Expenses/Expenses';
import Income from './components/Income/Income';
import Accounting from './components/Accounting/Accounting';
import Users from './components/Users/Users';
import Roles from './components/Roles/Roles';
import Customers from './components/Customers/Customers';
import Suppliers from './components/Suppliers/Suppliers';
import NormalSale from './components/NormalSale/NormalSale';
import ModuleSettings from './components/ModuleSettings/ModuleSettings';
import Invoices from './components/Invoices/Invoices';
import Branches from './components/Branches/Branches';
import Installation from './components/Installation/Installation';

// Protected Route component
const ProtectedRoute = ({ children }) => {
  // Check if user has valid JWT token
  const accessToken = localStorage.getItem('access_token');
  const isAuthenticated = accessToken && localStorage.getItem('isAuthenticated') === 'true';
  return isAuthenticated ? children : <Navigate to="/login" />;
};

function App() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    // Subscribe to toast notifications globally
    const unsubscribe = subscribeToToasts((newToast) => {
      setToasts(prev => [...prev, newToast]);
    });
    
    return () => unsubscribe();
  }, []);

  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  return (
    <Router>
      <div className="App">
        <ToastContainer toasts={toasts} removeToast={removeToast} />
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
      </div>
    </Router>
  );
}

export default App;
