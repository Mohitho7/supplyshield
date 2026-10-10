import React from 'react';
import { useScenario } from '../context/useScenario';

export const StrategyBenchmark: React.FC = () => {
  const {
    shutdownDays,
    horizonDays,
    seed,
    setPage,
    candidates,
    scenarioData,
    selectedCandidateId,
    plannerDecision,
  } = useScenario();

  const agent = candidates.find((c) => c.id === 'agent') || candidates[0];
  const opt = candidates.find((c) => c.id === 'optimized') || candidates[1];
  const base = candidates.find((c) => c.id === 'reorder') || candidates[2];

  const selectedPlan = candidates.find((c) => c.id === selectedCandidateId) || agent;

  return (
    <section className="page" id="page-benchmark" aria-label="Strategy benchmark">
      <div className="page-head">
        <div>
          <div className="eyebrow">Compare on equal terms</div>
          <h1>Strategy benchmark</h1>
          <p className="subtitle">
            Compare strategies under the identical scenario. Evaluate both total aggregate fulfillment and
            which specific product absorbs the component shortfall.
          </p>
        </div>
        <button
          className="btn"
          type="button"
          onClick={() => setPage('scenario')}
        >
          Change scenario →
        </button>
      </div>

      {/* Snapshot Alert if estimate */}
      {!scenarioData.isVerifiedSnapshot && (
        <div className="warning-note" style={{ marginBottom: '14px', padding: '10px 14px' }}>
          <strong>Demo Notice:</strong> Duration {shutdownDays} days is calculated from reference interpolation.
          Documented verified reference snapshots are available for <strong>1 day</strong>, <strong>7 days</strong>, and <strong>14 days</strong>.
        </div>
      )}

      {/* Mini KPIs */}
      <div className="mini-kpis" style={{ marginBottom: '16px' }}>
        <article className="panel metric">
          <div className="metric-label">Total demand</div>
          <div className="metric-value">1,680</div>
          <div className="metric-note">80 units/day × 21 days</div>
        </article>

        <article className="panel metric">
          <div className="metric-label">Best aggregate fill</div>
          <div className="metric-value">{agent.aggregateFillRatePct.toFixed(2)}%</div>
          <div className="metric-note">Agent-assisted & optimizer tie on volume</div>
        </article>

        <article className="panel metric">
          <div className="metric-label">Lowest unmet demand</div>
          <div className="metric-value">
            {agent.unmetDemandUnits} <span style={{ fontSize: '13px' }}>units</span>
          </div>
          <div className="metric-note">Both feasible strategies</div>
        </article>

        <article className="panel metric">
          <div className="metric-label">Active selected plan</div>
          <div className="metric-value" style={{ fontSize: '20px' }}>
            {selectedPlan.name}
          </div>
          <div className="metric-note">
            Status: {plannerDecision.replace('_', ' ')}
          </div>
        </article>
      </div>

      {/* PRIORITY 4: SHOW KEY TRADE-OFFS BEFORE THE DETAILED TABLE */}
      <section className="panel" style={{ marginBottom: '16px', borderLeft: '4px solid var(--accent)' }}>
        <div className="panel-head">
          <div>
            <h2>Strategic Trade-Offs at a Glance</h2>
            <p>Understand how strategy mechanics differ before inspecting line-item metrics.</p>
          </div>
          <span className="status status-info">Key Insights</span>
        </div>
        <div className="panel-body">
          <div className="grid grid-3" style={{ gap: '14px' }}>
            <div style={{ padding: '12px', background: 'var(--surface-2)', borderRadius: '8px' }}>
              <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '4px' }}>
                Trade-off 1 · Allocation Priority
              </div>
              <strong style={{ fontSize: '13px', display: 'block', marginBottom: '4px' }}>
                Aggregate fill rate hides product priority
              </strong>
              <p className="body-copy" style={{ margin: 0, fontSize: '12px' }}>
                Agent-assisted and optimized strategies fulfill the exact same total volume (85.42%),
                but Agent-assisted intentionally prioritizes PROD-01 (91.53% vs 85.19%), protecting high-margin contract SLAs.
              </p>
            </div>

            <div style={{ padding: '12px', background: 'var(--surface-2)', borderRadius: '8px' }}>
              <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--warn)', textTransform: 'uppercase', marginBottom: '4px' }}>
                Trade-off 2 · Cost vs Service
              </div>
              <strong style={{ fontSize: '13px', display: 'block', marginBottom: '4px' }}>
                Lowest cost is not the optimal decision
              </strong>
              <p className="body-copy" style={{ margin: 0, fontSize: '12px' }}>
                Reorder baseline registers lower spend (₹12,060 vs ₹16,470) solely because its order attempts
                during the blackout are rejected, producing 580 unmet demand units.
              </p>
            </div>

            <div style={{ padding: '12px', background: 'var(--surface-2)', borderRadius: '8px' }}>
              <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--danger)', textTransform: 'uppercase', marginBottom: '4px' }}>
                Trade-off 3 · Feasibility Rule
              </div>
              <strong style={{ fontSize: '13px', display: 'block', marginBottom: '4px' }}>
                Infeasible baseline is disqualified
              </strong>
              <p className="body-copy" style={{ margin: 0, fontSize: '12px' }}>
                The reorder baseline is kept visible strictly to show why standard ERP replenishment logic fails
                during supplier disruptions. It is never selectable or approvable.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Side-by-Side Comparison Table */}
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Side-by-side results</h2>
            <p>
              Shutdown duration {shutdownDays} days · horizon {horizonDays} days · seed {seed} ·{' '}
              {scenarioData.isVerifiedSnapshot ? 'Verified reference data' : 'Demo estimate'}
            </p>
          </div>
          <span className={`status ${scenarioData.isVerifiedSnapshot ? 'status-good' : 'status-warning'}`}>
            {scenarioData.isVerifiedSnapshot ? 'Verified snapshot' : 'Demo estimate'}
          </span>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Reorder baseline</th>
                <th>OR-Tools optimizer</th>
                <th>Agent-assisted</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Feasibility</strong></td>
                <td>
                  <span className="status status-danger">Infeasible</span>
                </td>
                <td>
                  <span className="status status-good">Valid</span>
                </td>
                <td>
                  <span className="status status-good">Valid</span>
                </td>
              </tr>

              <tr>
                <td>Aggregate fill rate</td>
                <td>{base.aggregateFillRatePct.toFixed(2)}%</td>
                <td>{opt.aggregateFillRatePct.toFixed(2)}%</td>
                <td><strong>{agent.aggregateFillRatePct.toFixed(2)}%</strong></td>
              </tr>

              <tr>
                <td>PROD-01 fulfilled / demand</td>
                <td>{base.prod1Fulfilled} / {base.prod1Demand}</td>
                <td>{opt.prod1Fulfilled} / {opt.prod1Demand}</td>
                <td><strong>{agent.prod1Fulfilled} / {agent.prod1Demand}</strong></td>
              </tr>

              <tr>
                <td>PROD-01 fill rate</td>
                <td>{base.prod1FillRatePct.toFixed(2)}%</td>
                <td>{opt.prod1FillRatePct.toFixed(2)}%</td>
                <td><strong style={{ color: 'var(--good)' }}>{agent.prod1FillRatePct.toFixed(2)}%</strong></td>
              </tr>

              <tr>
                <td>PROD-02 fulfilled / demand</td>
                <td>{base.prod2Fulfilled} / {base.prod2Demand}</td>
                <td>{opt.prod2Fulfilled} / {opt.prod2Demand}</td>
                <td>{agent.prod2Fulfilled} / {agent.prod2Demand}</td>
              </tr>

              <tr>
                <td>PROD-02 fill rate</td>
                <td>{base.prod2FillRatePct.toFixed(2)}%</td>
                <td>{opt.prod2FillRatePct.toFixed(2)}%</td>
                <td>{agent.prod2FillRatePct.toFixed(2)}%</td>
              </tr>

              <tr>
                <td>Unmet demand</td>
                <td>{base.unmetDemandUnits} units</td>
                <td>{opt.unmetDemandUnits} units</td>
                <td><strong>{agent.unmetDemandUnits} units</strong></td>
              </tr>

              <tr>
                <td>Landed cost</td>
                <td>₹{base.landedCostInr.toLocaleString('en-IN')}*</td>
                <td>₹{opt.landedCostInr.toLocaleString('en-IN')}</td>
                <td>₹{agent.landedCostInr.toLocaleString('en-IN')}</td>
              </tr>

              <tr>
                <td>Recovery milestone</td>
                <td>Day {base.recoveryDay}</td>
                <td>Day {opt.recoveryDay}</td>
                <td>Day {agent.recoveryDay}</td>
              </tr>

              <tr>
                <td>Coordinator score</td>
                <td><span className="muted">Not ranked</span></td>
                <td>{opt.score !== null ? opt.score.toLocaleString() : '—'}</td>
                <td><strong style={{ color: 'var(--good)' }}>{agent.score !== null ? agent.score.toLocaleString() : '—'}</strong></td>
              </tr>

              <tr>
                <td>Selectable for execution</td>
                <td>
                  <span className="status status-danger">No (Violations)</span>
                </td>
                <td>
                  <span className="status status-good">Yes</span>
                </td>
                <td>
                  <span className="status status-good">Yes (Recommended)</span>
                </td>
              </tr>

              <tr>
                <td>Data verification status</td>
                <td>
                  <span className={base.isVerified ? 'status status-info' : 'status status-warning'}>
                    {base.isVerified ? 'Verified benchmark' : 'Demo estimate'}
                  </span>
                </td>
                <td>
                  <span className={opt.isVerified ? 'status status-good' : 'status status-warning'}>
                    {opt.isVerified ? 'Verified snapshot' : 'Demo estimate'}
                  </span>
                </td>
                <td>
                  <span className={agent.isVerified ? 'status status-good' : 'status status-warning'}>
                    {agent.isVerified ? 'Verified snapshot' : 'Demo estimate'}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="panel-footer">
          *The reorder baseline appears cheaper only because its order attempts during the blackout are
          rejected by the supplier, leaving unfulfilled customer demand. It is strictly non-selectable.
        </div>
      </section>

      {/* Model Scope Below Table */}
      <section className="panel section-gap">
        <div className="panel-head">
          <div>
            <h2>Simulator model scope & boundaries</h2>
            <p>Explicit documentation of operational assumptions.</p>
          </div>
        </div>
        <div className="panel-body">
          <ul style={{ paddingLeft: '18px', margin: 0, display: 'grid', gap: '8px', color: 'var(--muted)', fontSize: '12px' }}>
            <li>
              <strong>Deterministic horizon:</strong> Fixed 21-day planning window and reproducible random seed (42).
            </li>
            <li>
              <strong>Lost-service convention:</strong> Unfulfilled daily demand contributes directly to period loss; no accumulating backlog queue.
            </li>
            <li>
              <strong>Downstream scope:</strong> Factory throughput and regional DC transfer times are unconstrained topology metadata.
            </li>
            <li>
              <strong>No external execution:</strong> Simulation environment only. No live purchasing orders, ERP webhooks, or vendor communications.
            </li>
          </ul>
        </div>
      </section>

      <div className="footnote">
        <span>SupplyShield AI · Operational decision-support benchmark</span>
        <span>Transparent scoring · Evidence first · Human decision third</span>
      </div>
    </section>
  );
};
