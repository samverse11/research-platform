// frontend/src/context/AuthContext.js
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { toast } from 'react-toastify';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('rp_token');
    const savedUser = localStorage.getItem('rp_user');
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('rp_token');
        localStorage.removeItem('rp_user');
      }
    }
    setLoading(false);

    const handleSessionExpired = () => {
      setToken(null);
      setUser(null);
      toast.error("Session expired. Please login again.");
    };

    window.addEventListener('session-expired', handleSessionExpired);
    return () => window.removeEventListener('session-expired', handleSessionExpired);
  }, []);

  const login = useCallback((newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('rp_token', newToken);
    localStorage.setItem('rp_user', JSON.stringify(newUser));
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('rp_token');
    localStorage.removeItem('rp_user');
  }, []);

  const isAuthenticated = !!token && !!user;

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export default AuthContext;
