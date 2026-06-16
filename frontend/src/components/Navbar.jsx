import React from 'react';
import { NavLink } from 'react-router-dom';
import { Leaf, Activity, Map, Menu } from 'lucide-react';
import './Navbar.css';

export const Navbar = () => {
  return (
    <nav className="navbar glass-panel">
      <div className="navbar-brand">
        <Leaf className="brand-icon pulse-primary" size={24} />
        <h1>ArborWatch</h1>
      </div>
      <div className="navbar-links">
        <NavLink to="/" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>
          <Activity size={18} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/map" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>
          <Map size={18} />
          <span>Risk Map</span>
        </NavLink>
      </div>
      <div className="navbar-mobile">
        <Menu size={24} />
      </div>
    </nav>
  );
};
