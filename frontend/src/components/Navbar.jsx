import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Leaf, Activity, Map, Menu, X } from 'lucide-react';
import './Navbar.css';

export const Navbar = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  return (
    <nav className="navbar glass-panel">
      <div className="navbar-brand">
        <Leaf className="brand-icon pulse-primary" size={24} />
        <h1>ArborWatch</h1>
      </div>

      {/* Desktop links */}
      <div className="navbar-links">
        <NavLink to="/" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          <Activity size={18} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/map" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          <Map size={18} />
          <span>Risk Map</span>
        </NavLink>
      </div>

      {/* Mobile hamburger toggle */}
      <button
        className="navbar-mobile"
        onClick={() => setMenuOpen(prev => !prev)}
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={menuOpen}
      >
        {menuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="navbar-drawer" role="menu">
          <NavLink
            to="/"
            className={({ isActive }) => isActive ? 'drawer-link active' : 'drawer-link'}
            onClick={closeMenu}
          >
            <Activity size={18} />
            <span>Dashboard</span>
          </NavLink>
          <NavLink
            to="/map"
            className={({ isActive }) => isActive ? 'drawer-link active' : 'drawer-link'}
            onClick={closeMenu}
          >
            <Map size={18} />
            <span>Risk Map</span>
          </NavLink>
        </div>
      )}
    </nav>
  );
};
