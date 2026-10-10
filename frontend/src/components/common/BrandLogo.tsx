import React from 'react';

interface BrandLogoProps {
  showSubtitle?: boolean;
  size?: number;
  className?: string;
}

export const BrandLogo: React.FC<BrandLogoProps> = ({
  showSubtitle = true,
  size = 32,
  className = '',
}) => {
  return (
    <div
      className={`brand-identity ${className}`}
      style={{ display: 'flex', alignItems: 'center', gap: '10px' }}
      aria-label="SupplyShield AI"
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))' }}
        aria-hidden="true"
      >
        <path
          d="M16 2.5L4.5 7V15C4.5 22.2 9.5 28.2 16 30C22.5 28.2 27.5 22.2 27.5 15V7L16 2.5Z"
          fill="#1b2a37"
          stroke="#e6b72e"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M9.5 15L14 19.5L23 9.5"
          stroke="#e6b72e"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="9.5" cy="15" r="1.8" fill="#ffd54f" />
        <circle cx="14" cy="19.5" r="1.8" fill="#ffd54f" />
        <circle cx="23" cy="9.5" r="1.8" fill="#ffd54f" />
        <path d="M14 19.5L16 24.5" stroke="#66d6b2" strokeWidth="1.4" strokeDasharray="1.5 1.5" />
        <circle cx="16" cy="24.5" r="1.4" fill="#66d6b2" />
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.15 }}>
        <span style={{ fontSize: '15px', fontWeight: 800, color: '#ffffff', letterSpacing: '0.04em' }}>
          SupplyShield <span style={{ color: '#e6b72e', fontWeight: 700 }}>AI</span>
        </span>
        {showSubtitle && (
          <span
            style={{
              fontSize: '8.5px',
              fontWeight: 700,
              color: '#81939e',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              marginTop: '3px',
            }}
          >
            Supply Chain Resilience
          </span>
        )}
      </div>
    </div>
  );
};
