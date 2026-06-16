import React from 'react';
import './Button.css';

export const Button = ({ children, onClick, variant = 'primary', className = '', ...props }) => {
  return (
    <button 
      className={`ui-button variant-${variant} ${className}`} 
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
};
