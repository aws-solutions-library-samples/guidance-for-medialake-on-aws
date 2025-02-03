import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../common/hooks/auth-context';

interface ProtectedRouteProps {
    children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
    const { isAuthenticated } = useAuth();
    return isAuthenticated ? <>{children}</> : <Navigate to="/sign-in" replace />;
};