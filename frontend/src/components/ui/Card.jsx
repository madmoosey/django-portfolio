import React from 'react';
import './Card.css';

export const Card = ({ children, className = '' }) => {
  return (
    <div className={`glass-panel ui-card ${className}`}>
      {children}
    </div>
  );
};
