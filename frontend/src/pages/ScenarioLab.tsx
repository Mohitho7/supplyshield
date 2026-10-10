import React from 'react';
import { useScenario } from '../context/useScenario';

export const ScenarioLab: React.FC = () => {
  const {
    shutdownDays,
    setShutdownDays,
    scenarioData,
    scenarioId,
    setPage,
    isLoading,
  } = useScenario();

  const prod1 = scenarioData.products['PROD-01'];
  const prod2 = scenarioData.products['PROD-02'];

  return (
    <section className="page" id="page-scenario" aria-label="Scenario lab">
      <div className="page-head">
        <div>
          <div className="eyebrow">Explore before deciding</div>
          <h1>Scenario lab</h1>
          <p className="subtitle">
            Configure the supplier disruption duration and inspect immediate projected outcomes.
            All metrics and scenario identities update atomically across the application.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span
            className={`status ${scenarioData.isVerifiedSnapshot ? 'status-good' : 'status-warning'}`}
          >
            {scenarioData.isVerifiedSnapshot ? 'Verified snapshot' : 'Demo estimate'}
          </span>
          <span className="status status-info">Fixed horizon · 21 days</span>
        </div>
      </div>

      {/* PRIORITY 4: CONTROLS & PROJECTED METRICS FIRST */}
      <div className="grid grid-2">
        {/* Left: Interactive Scenario Controls */}
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Scenario configuration</h2>
              <p>Adjust primary supplier outage duration (1–14 days).</p>
            </div>
            <span className="scenario-pill">{scenarioId}</span>
          </div>

          <div className="panel-body" style={{ display: 'grid', gap: '16px' }}>
            <div className="field">
              <label htmlFor="shutdownSelect">Primary supplier shutdown duration (1–14 days)</label>
              <select
                id="shutdownSelect"
                value={shutdownDays}
                disabled={isLoading}
                onChange={(e) => setShutdownDays(Number(e.target.value))}
              >
                {Array.from({ length: 14 }, (_, i) => i + 1).map((day) => (
                  <option key={day} value={day}>
                    {day} day{day > 1 ? 's' : ''}{' '}
                    {day === 1 ? '— short disruption (verified)' : day === 7 ? '— baseline reference (verified)' : day === 14 ? '— severe disruption (verified)' : '— demo estimate'}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--muted)', marginBottom: '6px' }}>
                Quick scenario presets:
              </div>
              <div className="preset-row">
                <button
                  type="button"
                  className="preset"
                  data-duration="1"
                  aria-pressed={shutdownDays === 1}
                  onClick={() => setShutdownDays(1)}
                  disabled={isLoading}
                >
                  1 day (Short)
                </button>
                <button
                  type="button"
                  className="preset"
                  data-duration="7"
                  aria-pressed={shutdownDays === 7}
                  onClick={() => setShutdownDays(7)}
                  disabled={isLoading}
                >
                  7 days · baseline
                </button>
                <button
                  type="button"
                  className="preset"
                  data-duration="14"
                  aria-pressed={shutdownDays === 14}
                  onClick={() => setShutdownDays(14)}
                  disabled={isLoading}
                >
                  14 days (Severe)
                </button>
              </div>
            </div>

            <dl className="detail-list">
              <dt>Disrupted supplier</dt>
              <dd>SUP-01 (Primary)</dd>
              <dt>Alternate supplier</dt>
              <dd>SUP-02 (60 units/day cap)</dd>
              <dt>Planning horizon</dt>
              <dd>21 days</dd>
              <dt>Daily total demand</dt>
              <dd>80 units (PROD-01: 45, PROD-02: 35)</dd>
              <dt>Verification state</dt>
              <dd>
                {scenarioData.isVerifiedSnapshot
                  ? 'Verified reference snapshot'
                  : 'Interpolated demo estimate'}
              </dd>
            </dl>

            <div className="warning-note" style={{ margin: 0, padding: '10px 12px' }}>
              {scenarioData.isVerifiedSnapshot ? (
                <>
                  <strong>Verified reference data:</strong> Exact documented benchmark metrics loaded for duration {shutdownDays} days.
                </>
              ) : (
                <>
                  <strong>Demo estimate:</strong> Intermediate duration {shutdownDays} days is calculated via reference interpolation.
                  Connect the FastAPI backend to calculate verified mathematical results.
                </>
              )}
            </div>
          </div>
        </section>

        {/* Right: Key Projected Metrics */}
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Key projected metrics</h2>
              <p>Expected outcome for selected {shutdownDays}-day outage.</p>
            </div>
            <span
              className={`status ${
                scenarioData.isVerifiedSnapshot ? 'status-good' : 'status-warning'
              }`}
              id="scenarioType"
            >
              {scenarioData.typeLabel}
            </span>
          </div>

          <div className="panel-body">
            <div className="scenario-summary">
              <div className="summary-cell">
                <span>Aggregate fill</span>
                <strong id="scenarioFill">{scenarioData.aggregateFillRatePct.toFixed(2)}%</strong>
              </div>
              <div className="summary-cell">
                <span>Unmet demand</span>
                <strong id="scenarioUnmet">{scenarioData.unmetDemandUnits} units</strong>
              </div>
              <div className="summary-cell">
                <span>Recovery</span>
                <strong id="scenarioRecovery">Day {scenarioData.recoveryDay}</strong>
              </div>
            </div>

            <div className="grid grid-2 section-gap" style={{ gap: '10px' }}>
              <article className="panel metric">
                <div className="metric-label">Landed cost</div>
                <div className="metric-value" style={{ fontSize: '24px' }}>
                  ₹{scenarioData.landedCostInr.toLocaleString('en-IN')}
                </div>
                <div className="metric-note">Estimated landed procurement</div>
              </article>

              <article className="panel metric">
                <div className="metric-label">Scenario identity</div>
                <div
                  className="metric-value"
                  style={{ fontSize: '15px', letterSpacing: 0, overflowWrap: 'anywhere' }}
                >
                  {scenarioId}
                </div>
                <div className="metric-note">Deterministic identifier</div>
              </article>
            </div>

            <div className="section-gap">
              <div className="inline-heading">
                <strong className="small">Product-level service</strong>
                <span className="micro muted">Fulfilled / Demand</span>
              </div>

              <div id="scenarioProducts">
                <div className="product-row">
                  <div>
                    <div className="product-title">PROD-01 (Priority)</div>
                    <div className="product-meta">
                      {prod1.fulfilled} / {prod1.demand} fulfilled ({prod1.unmet} unmet)
                    </div>
                  </div>
                  <div className="meter">
                    <span style={{ width: `${Math.min(100, prod1.fillRatePct)}%` }} />
                  </div>
                  <div className="percent">{prod1.fillRatePct.toFixed(2)}%</div>
                </div>

                <div className="product-row">
                  <div>
                    <div className="product-title">PROD-02 (Standard)</div>
                    <div className="product-meta">
                      {prod2.fulfilled} / {prod2.demand} fulfilled ({prod2.unmet} unmet)
                    </div>
                  </div>
                  <div className="meter danger">
                    <span style={{ width: `${Math.min(100, prod2.fillRatePct)}%` }} />
                  </div>
                  <div className="percent">{prod2.fillRatePct.toFixed(2)}%</div>
                </div>
              </div>
            </div>

            <div style={{ marginTop: '16px' }}>
              <button
                className="btn btn-primary"
                type="button"
                style={{ width: '100%' }}
                onClick={() => setPage('recovery')}
              >
                Review Recovery Plans for this Scenario →
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Guide Section Below */}
      <section className="panel section-gap">
        <div className="panel-head">
          <div>
            <h2>How to read this scenario</h2>
            <p>Keep the cause, operational impact, and decision context together.</p>
          </div>
        </div>
        <div className="panel-body grid grid-3">
          <div className="step" style={{ borderTop: 0, padding: 0 }}>
            <span className="step-number">1</span>
            <div>
              <strong>Disruption cause</strong>
              <p>SUP-01 is unavailable for Days 1 through {shutdownDays} of the 21-day planning horizon.</p>
            </div>
          </div>
          <div className="step" style={{ borderTop: 0, padding: 0 }}>
            <span className="step-number">2</span>
            <div>
              <strong>Operational impact</strong>
              <p>Opening inventory buffers demand initially; alternate supplier lead time (4d) shapes shortages.</p>
            </div>
          </div>
          <div className="step" style={{ borderTop: 0, padding: 0 }}>
            <span className="step-number">3</span>
            <div>
              <strong>Candidate response</strong>
              <p>Compare plans on aggregate volume, priority allocation protection, and cost implications.</p>
            </div>
          </div>
        </div>
      </section>

      <div className="footnote">
        <span>UX principle: Scenario identity and metrics stay synchronized atomically.</span>
        <span>Planning aid only · external execution disabled</span>
      </div>
    </section>
  );
};
