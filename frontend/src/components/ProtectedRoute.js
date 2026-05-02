// frontend/src/components/ProtectedRoute.js
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  React.useEffect(() => {
    if (!loading && !isAuthenticated) {
      toast.info("Please login to continue using the platform.", { toastId: 'auth-protect' });
    }
  }, [isAuthenticated, loading]);

  if (loading) {
    return (
      <div style={{
        minHeight: '60vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#888',
        fontSize: '1.1em',
      }}>
        Loading...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default ProtectedRoute;
