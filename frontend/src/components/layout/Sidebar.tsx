import React from 'react';
import { useScenario } from '../../context/useScenario';
import type { PageId } from '../../types';

interface NavItem {
  id: PageId;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'command', label: 'Command center', icon: '◫' },
  { id: 'scenario', label: 'Scenario lab', icon: '⌘' },
  { id: 'network', label: 'Supply network', icon: '☍' },
  { id: 'sourcing', label: 'Supplier capacity', icon: '◇' },
  { id: 'recovery', label: 'Recovery workspace', icon: '⛨' },
  { id: 'benchmark', label: 'Strategy benchmark', icon: '▥' },
];

export const Sidebar: React.FC = () => {
  const { page, setPage, horizonDays, seed } = useScenario();

  return (
    <aside className="sidebar" aria-label="Application navigation">
      <div>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">S</span>
          <span>
            SUPPLYSHIELD <span style={{ fontWeight: 500, opacity: 0.68 }}>AI</span>
          </span>
        </div>

        <div className="side-label" style={{ marginTop: '29px' }}>
          Decision workspace
        </div>

        <nav className="nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const isActive = page === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setPage(item.id)}
                aria-current={isActive ? 'page' : undefined}
              >
                <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="side-foot">
        <strong>
          <span className="dot" style={{ color: 'var(--good)', marginRight: '6px' }} />
          Decision-support mode
        </strong>
        No real purchase orders are sent.
        <br />
        Model horizon: {horizonDays} days · Seed: {seed}
      </div>
    </aside>
  );
};
