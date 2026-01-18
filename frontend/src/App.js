// frontend/src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';

// Pages (we'll create these)
import HomePage from './pages/HomePage';
import SearchPage from './pages/SearchPage';
import SummarizePage from './pages/SummarizePage';
import LoginPage from './pages/LoginPage';

function App() {
  return (
    <Router>
      <div className="App">
        {/* Navigation */}
        <nav className="navbar">
          <div className="nav-container">
            <Link to="/" className="nav-logo">
              🔬 Research Platform
            </Link>
            <ul className="nav-menu">
              <li><Link to="/" className="nav-link">Home</Link></li>
              <li><Link to="/search" className="nav-link">Search Papers</Link></li>
              <li><Link to="/summarize" className="nav-link">Summarize</Link></li>
              <li><Link to="/login" className="nav-link">Login</Link></li>
            </ul>
          </div>
        </nav>

        {/* Routes */}
        <div className="content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/summarize" element={<SummarizePage />} />
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;