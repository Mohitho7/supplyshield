import React from 'react';
import { useScenario } from '../../context/useScenario';

export const Toast: React.FC = () => {
  const { toastMessage } = useScenario();

  if (!toastMessage) return null;

  return (
    <div className="toast" role="status" aria-live="polite">
      <span className="dot" style={{ backgroundColor: 'var(--accent)' }} />
      <span>{toastMessage}</span>
    </div>
  );
};
