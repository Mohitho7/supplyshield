import React from 'react';
import { useScenario } from '../context/useScenario';

export const SupplierCapacity: React.FC = () => {
  const { shutdownDays, setPage } = useScenario();

  return (
    <section className="page" id="page-sourcing" aria-label="Supplier capacity">
      <div className="page-head">
        <div>
          <div className="eyebrow">Capacity and cost context</div>
          <h1>Supplier capacity</h1>
          <p className="subtitle">
            Understand what each modeled supplier can provide. The model specifies operational constraints,
            lead times, and costs—not live supplier RFQs or fictitious vendor quotes.
          </p>
        </div>
        <span className="status status-info">Model inputs only</span>
      </div>

      <div className="grid grid-equal">
        {/* Primary Supplier */}
        <article className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">SUP-01</div>
              <h2 style={{ marginTop: '5px' }}>Primary supplier</h2>
              <p>Critical tier 1 source unavailable during the blackout window.</p>
            </div>
            <span className="status status-danger">Disrupted</span>
          </div>

          <div className="panel-body">
            <div className="scenario-summary">
              <div className="summary-cell">
                <span>Daily capacity</span>
                <strong>100 units</strong>
              </div>
              <div className="summary-cell">
                <span>Lead time</span>
                <strong>2 days</strong>
              </div>
              <div className="summary-cell">
                <span>Landed unit cost</span>
                <strong>₹12.00</strong>
              </div>
            </div>

            <div className="section-gap">
              <div className="inline-heading">
                <strong className="small">Scenario availability</strong>
                <span className="micro muted">{shutdownDays}-day blackout</span>
              </div>
              <div className="meter danger">
                <span style={{ width: '0%' }} />
              </div>
              <p className="body-copy" style={{ marginTop: '8px' }}>
                Unavailable on Days 1–{shutdownDays} in this scenario. Any candidate order schedule attempting
                to purchase from SUP-01 during this period is marked <strong>infeasible</strong>.
              </p>
            </div>
          </div>
        </article>

        {/* Alternate Supplier */}
        <article className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">SUP-02</div>
              <h2 style={{ marginTop: '5px' }}>Alternate supplier</h2>
              <p>Operational backup with higher cost, longer lead time, and capped output.</p>
            </div>
            <span className="status status-warning">Constrained</span>
          </div>

          <div className="panel-body">
            <div className="scenario-summary">
              <div className="summary-cell">
                <span>Daily capacity</span>
                <strong>60 units</strong>
              </div>
              <div className="summary-cell">
                <span>Lead time</span>
                <strong>4 days</strong>
              </div>
              <div className="summary-cell">
                <span>Landed unit cost</span>
                <strong>₹16.50</strong>
              </div>
            </div>

            <div className="section-gap">
              <div className="inline-heading">
                <strong className="small">Capacity vs total daily demand</strong>
                <span className="micro muted">60 / 80 units (75%)</span>
              </div>
              <div className="meter">
                <span style={{ width: '75%' }} />
              </div>
              <p className="body-copy" style={{ marginTop: '8px' }}>
                At 60 units/day, the backup supplier cannot independently satisfy total network demand
                (80 units/day). Even at maximum capacity utilization, an unfulfilled deficit emerges once opening
                inventory runs out.
              </p>
            </div>
          </div>
        </article>
      </div>

      <div className="warning-note section-gap">
        <strong>Data integrity policy:</strong> We do not display fabricated commercial quotes, fake supplier
        on-time delivery scores, or simulated live RFQ expiration timers. The simulator strictly evaluates
        plans against verified mathematical constraints.
      </div>

      {/* Sourcing Analysis & Next Steps */}
      <section className="panel section-gap">
        <div className="panel-head">
          <div>
            <h2>How capacity shapes recovery options</h2>
            <p>Grounding decision trade-offs in tangible operational constraints.</p>
          </div>
        </div>

        <div className="panel-body grid grid-3">
          <div>
            <h3>1. The capacity bottleneck</h3>
            <p className="body-copy">
              With SUP-02 capped at 60 units/day and 4-day delivery lead time, expediting orders cannot fully
              eliminate stockouts during an extended shutdown.
            </p>
          </div>
          <div>
            <h3>2. The cost trade-off</h3>
            <p className="body-copy">
              Landed cost increases from ₹12.00 to ₹16.50 per unit (+37.5%). Candidate evaluations calculate
              exact procurement expenditure based on simulated unit quantities.
            </p>
          </div>
          <div>
            <h3>3. Connect to plan evaluation</h3>
            <p className="body-copy">
              Inspect how the coordinator balances PROD-01 and PROD-02 allocations within the 60-unit constraint.
            </p>
            <button
              className="btn btn-primary"
              type="button"
              style={{ marginTop: '8px', width: '100%' }}
              onClick={() => setPage('recovery')}
            >
              Open recovery workspace →
            </button>
          </div>
        </div>
      </section>

      <div className="footnote">
        <span>Model parameters: deterministic lead times and capacity limits</span>
        <span>Decision-support mode · external purchasing disabled</span>
      </div>
    </section>
  );
};
