import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './App.css';

import HomePage      from './pages/HomePage';
import SearchPage    from './pages/SearchPage';
import SummarizePage from './pages/SummarizePage';
import TranslatePage from './pages/TranslatePage';
import LoginPage     from './pages/LoginPage';
import SignupPage    from './pages/SignupPage';
import AnalyzePage   from './pages/AnalyzePage';
import DashboardPage from './pages/DashboardPage';
import ProtectedRoute from './components/ProtectedRoute';

function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = React.useState(false);

  const handleLogout = () => {
    logout();
    toast.success("Successfully logged out.");
    setDropdownOpen(false);
    navigate('/');
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
  };

  const handleProtectedLinkClick = (e, path) => {
    if (!isAuthenticated) {
      e.preventDefault();
      toast.info("Please login to continue using the platform.", { toastId: 'nav-protect' });
      navigate('/login');
    } else {
      setDropdownOpen(false);
    }
  };

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          🔬 Research Platform
        </Link>
        <ul className="nav-menu">
          <li><Link to="/" className="nav-link">Home</Link></li>
          <li><Link to="/search" className="nav-link" onClick={(e) => handleProtectedLinkClick(e, '/search')}>Search Papers</Link></li>
          <li><Link to="/summarize" className="nav-link" onClick={(e) => handleProtectedLinkClick(e, '/summarize')}>Summarize</Link></li>
          <li><Link to="/translate" className="nav-link" onClick={(e) => handleProtectedLinkClick(e, '/translate')}>Translate</Link></li>
          <li><Link to="/analyze" className="nav-link" onClick={(e) => handleProtectedLinkClick(e, '/analyze')}>Analyze</Link></li>
          
          {isAuthenticated ? (
            <li className="nav-user-menu">
              <div className="avatar-wrapper" onClick={() => setDropdownOpen(!dropdownOpen)}>
                <div className="user-avatar">
                  {getInitials(user?.username)}
                </div>
                {dropdownOpen && (
                  <div className="avatar-dropdown">
                    <div className="dropdown-header">
                      <span className="dropdown-name">{user?.username}</span>
                      <span className="dropdown-email">{user?.email}</span>
                    </div>
                    <div className="dropdown-divider"></div>
                    <Link to="/dashboard" className="dropdown-item" onClick={() => setDropdownOpen(false)}>Dashboard</Link>
                    <Link to="/dashboard" className="dropdown-item" onClick={() => setDropdownOpen(false)}>History</Link>
                    <div className="dropdown-divider"></div>
                    <button className="dropdown-item logout-btn" onClick={handleLogout}>Logout</button>
                  </div>
                )}
              </div>
            </li>
          ) : (
            <li><Link to="/login" className="nav-link nav-link-login">Login</Link></li>
          )}
        </ul>
      </div>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <Navbar />
        <ToastContainer position="bottom-right" theme="dark" />
        <div className="content">
          <Routes>
            <Route path="/"          element={<HomePage />} />
            <Route path="/login"     element={<LoginPage />} />
            <Route path="/signup"    element={<SignupPage />} />
            
            {/* Protected Core Routes */}
            <Route path="/search"    element={<ProtectedRoute><SearchPage /></ProtectedRoute>} />
            <Route path="/summarize" element={<ProtectedRoute><SummarizePage /></ProtectedRoute>} />
            <Route path="/translate" element={<ProtectedRoute><TranslatePage /></ProtectedRoute>} />
            <Route path="/analyze"   element={<ProtectedRoute><AnalyzePage /></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;