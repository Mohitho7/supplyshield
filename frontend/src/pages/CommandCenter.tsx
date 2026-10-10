import React from 'react';
import { useScenario } from '../context/useScenario';

export const CommandCenter: React.FC = () => {
  const {
    scenarioData,
    shutdownDays,
    scenarioId,
    setPage,
    recommendedCandidateId,
    selectedCandidateId,
    plannerDecision,
    candidates,
  } = useScenario();

  const selectedCandidate =
    candidates.find((c) => c.id === selectedCandidateId) || candidates[0];
  const recommendedCandidate =
    candidates.find((c) => c.id === recommendedCandidateId) || candidates[0];

  const prod1Fulfilled = selectedCandidate.prod1Fulfilled;
  const prod1Demand = selectedCandidate.prod1Demand;
  const prod1FillPct = selectedCandidate.prod1FillRatePct;
  const prod1Unmet = prod1Demand - prod1Fulfilled;

  const prod2Fulfilled = selectedCandidate.prod2Fulfilled;
  const prod2Demand = selectedCandidate.prod2Demand;
  const prod2FillPct = selectedCandidate.prod2FillRatePct;
  const prod2Unmet = prod2Demand - prod2Fulfilled;

  const totalDemand = prod1Demand + prod2Demand;
  const totalFulfilled = prod1Fulfilled + prod2Fulfilled;

  return (
    <section className="page" id="page-command" aria-label="Command center">
      {/* PRIORITY 1: Top Incident, Scenario, Strategy, & Approval Status */}
      <div
        className="hero"
        style={{
          gridTemplateColumns: 'minmax(0, 1fr) 280px',
          marginBottom: '16px',
          padding: '22px 24px'
        }}
      >
        <div className="hero-copy">
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '8px' }}>
            <span className="status status-danger">
              SUP-01 Disrupted · Days 1–{shutdownDays} Outage
            </span>
            <span
              className="scenario-pill"
              id="heroScenarioPill"
              style={{
                background: 'rgba(230, 183, 46, 0.14)',
                borderColor: 'rgba(230, 183, 46, 0.45)',
                color: 'var(--accent, #e6b72e)',
                fontWeight: 800,
                fontFamily: 'monospace',
                fontSize: '12px'
              }}
            >
              Scenario: {scenarioId}
            </span>
            <span className="status status-good">
              Recommended: {recommendedCandidate.name} (Rank 1)
            </span>
            {plannerDecision === 'approved' && (
              <span className="status status-good">
                ✓ Decision: Approved by planner
              </span>
            )}
            {plannerDecision === 'rejected' && (
              <span className="status status-danger">
                ✕ Decision: Rejected by planner
              </span>
            )}
            {plannerDecision === 'awaiting_review' && (
              <span className="status status-warning">
                ⏳ Decision: Awaiting planner review
              </span>
            )}
          </div>

          <h2 style={{ fontSize: 'clamp(21px, 2.2vw, 28px)', margin: '6px 0 8px', maxWidth: '32ch' }}>
            Primary supply is disrupted. Which recovery plan protects the most critical product?
          </h2>
          <p style={{ margin: '0 0 16px', maxWidth: '68ch', fontSize: '13px', color: '#c1cbd1' }}>
            Primary supplier <strong>SUP-01</strong> is offline for {shutdownDays} days. The coordinator recommends{' '}
            <strong>{recommendedCandidate.name}</strong> to protect high-priority PROD-01 service without exceeding
            alternate supplier SUP-02 constraints.
          </p>

          {/* Prominent Decision Action CTA */}
          <div className="hero-actions" style={{ alignItems: 'center' }}>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => setPage('recovery')}
              style={{ fontSize: '13px', padding: '10px 18px', fontWeight: 800 }}
            >
              Review & Decide on Recovery Plan <span aria-hidden="true">→</span>
            </button>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => setPage('network')}
              style={{ fontSize: '13px' }}
            >
              Inspect Affected Network
            </button>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => setPage('scenario')}
              style={{ fontSize: '13px' }}
            >
              Adjust Outage Duration ({shutdownDays}d)
            </button>
          </div>
        </div>

        <div
          className="hero-status"
          style={{
            borderLeft: '1px solid #3d505b',
            paddingLeft: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            justifyContent: 'center'
          }}
        >
          {/* Dedicated Active Scenario Card */}
          <div
            className="hero-stat-card"
            id="heroActiveScenarioCard"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}
          >
            <div
              className="label"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                color: '#b4c1c9',
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 600
              }}
            >
              <span>Active Scenario</span>
              <span className="status status-info" style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '4px' }}>
                H21 · S42
              </span>
            </div>
            <div
              className="value"
              id="heroScenarioId"
              style={{
                fontSize: '15px',
                fontWeight: 800,
                fontFamily: 'monospace',
                color: 'var(--accent, #e6b72e)',
                marginTop: '4px',
                letterSpacing: '0.02em',
                wordBreak: 'break-all'
              }}
            >
              {scenarioId}
            </div>
            <div className="detail" style={{ fontSize: '11px', color: '#c1cbd1', marginTop: '3px' }}>
              {scenarioData.isVerifiedSnapshot ? 'Verified benchmark model' : 'Simulation model'} · 21d horizon
            </div>
          </div>

          <div
            className="hero-stat-card"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}
          >
            <div
              className="label"
              style={{
                color: '#b4c1c9',
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 600
              }}
            >
              Outage Duration
            </div>
            <div className="value" id="heroShutdown" style={{ fontSize: '20px', fontWeight: 800, marginTop: '2px' }}>
              {shutdownDays} days
            </div>
            <div className="detail" style={{ fontSize: '11px', color: '#c1cbd1', marginTop: '2px' }}>
              SUP-01 · from Day 1
            </div>
          </div>

          <div
            className="hero-stat-card"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}
          >
            <div
              className="label"
              style={{
                color: '#b4c1c9',
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 600
              }}
            >
              Planner Sign-Off
            </div>
            <div style={{ marginTop: '4px' }}>
              {plannerDecision === 'approved' ? (
                <span className="status status-good" style={{ fontSize: '11px' }}>Approved</span>
              ) : plannerDecision === 'rejected' ? (
                <span className="status status-danger" style={{ fontSize: '11px' }}>Rejected</span>
              ) : (
                <span className="status status-warning" style={{ fontSize: '11px' }}>Awaiting review</span>
              )}
            </div>
            <div className="detail" style={{ marginTop: '4px', fontSize: '11px', color: '#c1cbd1' }}>
              {plannerDecision === 'approved'
                ? 'Sign-off logged. Live PO dispatch disabled.'
                : 'Managerial review required.'}
            </div>
          </div>
        </div>
      </div>

      {/* Snapshot Verification Notice if estimated */}
      {!scenarioData.isVerifiedSnapshot && (
        <div className="warning-note" style={{ marginBottom: '14px', padding: '10px 14px' }}>
          <strong>Demo Notice:</strong> Duration {shutdownDays} days uses an unverified reference interpolation.
          Documented verified snapshots are available for <strong>1 day</strong>, <strong>7 days</strong>, and <strong>14 days</strong>.
        </div>
      )}

      {/* Four KPI Cards Immediately Below */}
      <div className="mini-kpis" id="commandKpis">
        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Aggregate fill rate</div>
            <span className="metric-icon" aria-hidden="true">↗</span>
          </div>
          <div className="metric-value">{selectedCandidate.aggregateFillRatePct.toFixed(2)}%</div>
          <div className="metric-note">
            {totalFulfilled.toLocaleString()} of {totalDemand.toLocaleString()} demand units fulfilled
          </div>
        </article>

        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Unmet demand</div>
            <span className="metric-icon" aria-hidden="true">!</span>
          </div>
          <div className="metric-value">
            {selectedCandidate.unmetDemandUnits}{' '}
            <span style={{ fontSize: '13px', letterSpacing: 0 }}>units</span>
          </div>
          <div className="metric-note">Period-specific unmet demand; lost-service convention</div>
        </article>

        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Landed procurement cost</div>
            <span className="metric-icon" aria-hidden="true">₹</span>
          </div>
          <div className="metric-value">₹{selectedCandidate.landedCostInr.toLocaleString('en-IN')}</div>
          <div className="metric-note">For selected {selectedCandidate.name}</div>
        </article>

        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Recovery day</div>
            <span className="metric-icon" aria-hidden="true">◷</span>
          </div>
          <div className="metric-value">Day {selectedCandidate.recoveryDay}</div>
          <div className="metric-note">First day modeled service is fully restored</div>
        </article>
      </div>

      {/* Product Impact & Next Steps */}
      <div className="grid grid-2">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Product service impact</h2>
              <p>Where fulfilled units go under {selectedCandidate.name}.</p>
            </div>
            <span className="status status-info">21-day horizon</span>
          </div>
          <div className="panel-body">
            <div className="product-row">
              <div>
                <div className="product-title">PROD-01 · Priority product</div>
                <div className="product-meta">
                  {prod1Fulfilled} fulfilled of {prod1Demand} demanded · {prod1Unmet} unmet
                </div>
              </div>
              <div>
                <div className="meter">
                  <span style={{ width: `${Math.min(100, prod1FillPct)}%` }} />
                </div>
              </div>
              <div className="percent">{prod1FillPct.toFixed(2)}%</div>
            </div>

            <div className="product-row">
              <div>
                <div className="product-title">PROD-02 · Standard product</div>
                <div className="product-meta">
                  {prod2Fulfilled} fulfilled of {prod2Demand} demanded · {prod2Unmet} unmet
                </div>
              </div>
              <div>
                <div className="meter danger">
                  <span style={{ width: `${Math.min(100, prod2FillPct)}%` }} />
                </div>
              </div>
              <div className="percent">{prod2FillPct.toFixed(2)}%</div>
            </div>

            <div className="layout-note" style={{ marginTop: '14px' }}>
              {selectedCandidateId === 'agent'
                ? 'The agent-assisted strategy prioritizes PROD-01 service (91.53%) while matching uniform optimizer aggregate volume.'
                : 'The uniform optimizer balances shortage evenly across products, resulting in lower PROD-01 service.'}
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Recommended next steps</h2>
              <p>The shortest route from disruption signal to an informed decision.</p>
            </div>
          </div>
          <div className="panel-body">
            <div className="step-list">
              <div className="step">
                <span className="step-number">1</span>
                <div>
                  <strong>Inspect candidate plans</strong>
                  <p>Compare Agent-assisted vs OR-Tools allocation trade-offs in the Recovery Workspace.</p>
                </div>
              </div>
              <div className="step">
                <span className="step-number">2</span>
                <div>
                  <strong>Verify operational feasibility</strong>
                  <p>Check supplier blackout rules, lead times, and capacity limitations.</p>
                </div>
              </div>
              <div className="step">
                <span className="step-number">3</span>
                <div>
                  <strong>Make a separate planner decision</strong>
                  <p>Advisory recommendation. Human approval is recorded without dispatching live purchase orders.</p>
                </div>
              </div>
            </div>
            <button
              className="btn btn-primary"
              type="button"
              style={{ width: '100%', marginTop: '5px' }}
              onClick={() => setPage('recovery')}
            >
              Open recovery workspace →
            </button>
          </div>
        </section>
      </div>

      {/* Strategy Snapshot Table */}
      <section className="panel section-gap">
        <div className="panel-head">
          <div>
            <h2>Strategy snapshot</h2>
            <p>Same scenario, same demand, different allocation behavior.</p>
          </div>
          <button
            className="btn"
            type="button"
            onClick={() => setPage('benchmark')}
          >
            View full benchmark →
          </button>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Aggregate fill</th>
                <th>PROD-01 fill</th>
                <th>Unmet units</th>
                <th>Landed cost</th>
                <th>Decision state</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((cand) => {
                const isPlanSelected = selectedCandidateId === cand.id;
                let badgeClass = 'status';
                let badgeText = cand.rankLabel;

                if (!cand.feasible) {
                  badgeClass = 'status status-danger';
                  badgeText = 'Benchmark only (Infeasible)';
                } else if (isPlanSelected) {
                  if (plannerDecision === 'approved') {
                    badgeClass = 'status status-good';
                    badgeText = 'Approved by planner';
                  } else if (plannerDecision === 'rejected') {
                    badgeClass = 'status status-danger';
                    badgeText = 'Rejected by planner';
                  } else {
                    badgeClass = 'status status-warning';
                    badgeText = 'Selected for review';
                  }
                }

                return (
                  <tr key={cand.id} className={isPlanSelected ? 'selected' : ''}>
                    <td>
                      <div className="strategy-name">
                        <strong>{cand.name}</strong>
                        <small>{cand.subtitle}</small>
                      </div>
                    </td>
                    <td>{cand.aggregateFillRatePct.toFixed(2)}%</td>
                    <td>{cand.prod1FillRatePct.toFixed(2)}%</td>
                    <td>{cand.unmetDemandUnits}</td>
                    <td>₹{cand.landedCostInr.toLocaleString('en-IN')}</td>
                    <td>
                      <span className={badgeClass}>{badgeText}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="panel-footer">
          Values dynamically updated for shutdown duration {shutdownDays} days ({scenarioId}).
          The reorder baseline violates the shutdown blackout rule and is never selectable.
        </div>
      </section>

      {/* Footnote */}
      <div className="footnote">
        <span>
          Scenario: <strong>{scenarioId}</strong> · {scenarioData.isVerifiedSnapshot ? 'verified reference snapshot' : 'interpolated estimate'}
        </span>
        <span>Planning aid only · external execution disabled</span>
      </div>
    </section>
  );
};
