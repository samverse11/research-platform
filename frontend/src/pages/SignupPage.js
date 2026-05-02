// frontend/src/pages/SignupPage.js
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import './LoginPage.css'; // shared auth styles

function SignupPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Redirect if already logged in
  React.useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isAuthenticated, navigate]);

  const validate = () => {
    if (!username.trim()) return 'Username is required';
    if (username.trim().length < 2) return 'Username must be at least 2 characters';
    if (!email.trim()) return 'Email is required';
    if (!email.includes('@')) return 'Enter a valid email address';
    if (!password) return 'Password is required';
    if (password.length < 6) return 'Password must be at least 6 characters';
    if (password !== confirmPassword) return 'Passwords do not match';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      const res = await api.auth.register({
        username: username.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      login(res.data.access_token, res.data.user);
      navigate('/dashboard');
    } catch (err) {
      console.error("Signup Error:", err);
      let msg = 'Registration failed. Please try again.';
      
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          msg = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          msg = detail[0].msg || 'Validation Error';
        }
      } else if (err.message) {
        msg = err.message;
      }
      
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-icon">🚀</div>
        <h1 className="auth-title">Create Account</h1>
        <p className="auth-subtitle">Join the research platform</p>

        {error && (
          <div className="auth-alert alert-error">
            <span>⚠</span> {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-field">
            <label className="auth-label">Username</label>
            <input
              type="text"
              className="auth-input"
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
            />
          </div>

          <div className="auth-field">
            <label className="auth-label">Email</label>
            <input
              type="email"
              className="auth-input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>

          <div className="auth-field">
            <label className="auth-label">Password</label>
            <input
              type="password"
              className="auth-input"
              placeholder="Min. 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>

          <div className="auth-field">
            <label className="auth-label">Confirm Password</label>
            <input
              type="password"
              className="auth-input"
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? (
              <>
                <span className="auth-spinner" />
                Creating Account...
              </>
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

export default SignupPage;
