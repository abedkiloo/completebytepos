import React from 'react';

export const BrowserRouter = ({ children }) => <div data-testid="router">{children}</div>;
export const Routes = ({ children }) => <>{children}</>;
export const Route = () => null;
export const Navigate = () => null;
export const useLocation = () => ({ pathname: '/login', search: '', state: null });
export const Outlet = () => null;
export const useNavigate = () => jest.fn();
export const Link = ({ children, to }) => <a href={to}>{children}</a>;
