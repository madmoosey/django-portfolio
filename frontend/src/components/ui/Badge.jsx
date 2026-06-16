import React from 'react';
import './Badge.css';

export const Badge = ({ children, variant = 'info', className = '' }) => {
  return (
    <span className={`ui-badge variant-${variant} ${className}`}>
      {children}
    </span>
  );
};
