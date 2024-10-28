import React, { createContext, useCallback, useContext, useState, useEffect } from 'react';
import { StorageHelper } from '../helpers/storage-helper';
import { useAuthenticate } from './authenticate';
import { useUserPool } from './userpool';

interface AuthContextType {
  isAuthenticated: boolean;
  setIsAuthenticated: (isAuthenticated: boolean) => void;
  checkAuthStatus: () => void;
  refreshSession: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { refreshSession: refreshAuthSession } = useAuthenticate();
  const { reinitializeUserPool } = useUserPool();

  const checkAuthStatus = useCallback(() => {
    const token = StorageHelper.getToken();
    if (token) {
      setIsAuthenticated(true);
    } else {
      setIsAuthenticated(false);
    }
    setIsLoading(false);
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      await refreshAuthSession();
      checkAuthStatus();
    } catch (error: unknown) {
      console.error('Failed to refresh session:', error);
      if (error instanceof Error && error.message === 'User pool is not initialized') {
        reinitializeUserPool();
        // Retry the refresh after re-initialization
        try {
          await refreshAuthSession();
          checkAuthStatus();
        } catch (retryError) {
          console.error('Failed to refresh session after re-initialization:', retryError);
          setIsAuthenticated(false);
          StorageHelper.clearToken();
        }
      } else {
        setIsAuthenticated(false);
        StorageHelper.clearToken();
      }
    }
  }, [refreshAuthSession, checkAuthStatus, reinitializeUserPool]);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, setIsAuthenticated, checkAuthStatus, refreshSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
