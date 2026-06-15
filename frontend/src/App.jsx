import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { Dashboard } from './pages/Dashboard';
import { MapViewer } from './pages/MapViewer';
import './index.css';

function App() {
  return (
    <Router>
      <div className="app-container" style={{ maxWidth: '1200px', margin: '0 auto', padding: '1rem' }}>
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/map" element={<MapViewer />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
