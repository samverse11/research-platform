import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';

import HomePage      from './pages/HomePage';
import SearchPage    from './pages/SearchPage';
import SummarizePage from './pages/SummarizePage';
import TranslatePage from './pages/TranslatePage';
import LoginPage     from './pages/LoginPage';
import AnalyzePage   from './pages/AnalyzePage';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="nav-container">
            <Link to="/" className="nav-logo">
              🔬 Research Platform
            </Link>
            <ul className="nav-menu">
              <li><Link to="/"          className="nav-link">Home</Link></li>
              <li><Link to="/search"    className="nav-link">Search Papers</Link></li>
              <li><Link to="/summarize" className="nav-link">Summarize</Link></li>
              <li><Link to="/translate" className="nav-link">Translate</Link></li>
              <li><Link to="/analyze"   className="nav-link">Analyze</Link></li>
              <li><Link to="/login"     className="nav-link">Login</Link></li>
            </ul>
          </div>
        </nav>

        <div className="content">
          <Routes>
            <Route path="/"          element={<HomePage />} />
            <Route path="/search"    element={<SearchPage />} />
            <Route path="/summarize" element={<SummarizePage />} />
            <Route path="/translate" element={<TranslatePage />} />
            <Route path="/analyze"   element={<AnalyzePage />} />
            <Route path="/login"     element={<LoginPage />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;