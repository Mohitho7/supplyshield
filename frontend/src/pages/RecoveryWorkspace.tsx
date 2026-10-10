import React from 'react';
import { useScenario } from '../context/useScenario';
import type { CandidateId } from '../types';

export const RecoveryWorkspace: React.FC = () => {
  const {
    scenarioId,
    shutdownDays,
    scenarioData,
    candidates,
    validationChecks,
    decisionTrace,
    recommendedCandidateId,
    inspectedCandidateId,
    setInspectedCandidateId,
    selectedCandidateId,
    selectPlanForReview,
    plannerDecision,
    approvePlan,
    rejectPlan,
    revokePlanDecision,
    plannerReviewNotes,
    setPlannerReviewNotes,
    showToast,
  } = useScenario();

  const inspectedCandidate =
    candidates.find((c) => c.id === inspectedCandidateId) || candidates[0];

  const selectedCandidate =
    candidates.find((c) => c.id === selectedCandidateId) || candidates[0];

  const recommendedCandidate =
    candidates.find((c) => c.id === recommendedCandidateId) || candidates[0];

  const handleInspect = (id: CandidateId) => {
    setInspectedCandidateId(id);
    const c = candidates.find((cand) => cand.id === id);
    showToast(`Inspecting ${c?.name || id} trace & validation.`);
  };

  return (
    <section className="page" id="page-recovery" aria-label="Recovery workspace">
      <div className="page-head">
        <div>
          <div className="eyebrow">Compare · validate · decide</div>
          <h1>Recovery workspace</h1>
          <p className="subtitle">
            Evaluate candidate evidence, expected impacts, and validation checks before recording an authorized
            planner decision.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className={`status ${scenarioData.isVerifiedSnapshot ? 'status-good' : 'status-warning'}`}>
            {scenarioData.isVerifiedSnapshot ? 'Verified snapshot' : 'Demo estimate'}
          </span>
          <span
            className={`status ${
              plannerDecision === 'approved'
                ? 'status-good'
                : plannerDecision === 'rejected'
                ? 'status-danger'
                : 'status-warning'
            }`}
          >
            {plannerDecision === 'approved'
              ? `Approved: ${selectedCandidate.name}`
              : plannerDecision === 'rejected'
              ? `Rejected: ${selectedCandidate.name}`
              : 'Awaiting planner review'}
          </span>
        </div>
      </div>

      {/* Snapshot Alert if estimate */}
      {!scenarioData.isVerifiedSnapshot && (
        <div className="warning-note" style={{ marginBottom: '14px', padding: '10px 14px' }}>
          <strong>Demo Notice:</strong> Duration {shutdownDays} days is calculated from reference interpolation.
          Documented verified snapshots are available for 1-day, 7-day, and 14-day scenarios.
        </div>
      )}

      {/* 1. COORDINATOR RECOMMENDATION & FEASIBILITY STATUS */}
      <div
        className="hero"
        style={{ gridTemplateColumns: 'minmax(0, 1fr) 260px', marginBottom: '14px', padding: '20px 24px' }}
      >
        <div className="hero-copy">
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '6px' }}>
            <span className="status status-good">
              Coordinator recommendation: {recommendedCandidate.name} (Rank 1)
            </span>
            <span className="status status-good">
              Feasibility: Valid & Modeled
            </span>
            <span className="scenario-pill">
              {scenarioId}
            </span>
          </div>

          <h2 style={{ fontSize: 'clamp(20px, 2.1vw, 26px)', margin: '4px 0 8px' }}>
            {recommendedCandidate.name} recommended for planner review
          </h2>
          <p style={{ margin: '0', maxWidth: '68ch', fontSize: '13px', color: '#c1cbd1' }}>
            The multi-agent coordinator prioritizes high-value PROD-01 service ({recommendedCandidate.prod1FillRatePct.toFixed(2)}%)
            while matching uniform mathematical programming volume. This recommendation is advisory for human managerial sign-off.
          </p>
        </div>

        <div className="hero-status" style={{ borderLeft: '1px solid #3d505b', paddingLeft: '20px' }}>
          <div>
            <div className="label">Recommended Candidate</div>
            <div className="value" style={{ fontSize: '18px' }}>CAND-AGENT-SD{shutdownDays}</div>
            <div className="detail">Agent-assisted · Rank 1</div>
          </div>
          <div style={{ marginTop: '8px' }}>
            <div className="label">Current Plan Selected for Sign-Off</div>
            <div className="detail" style={{ fontWeight: 800, color: '#e6b72e' }}>
              {selectedCandidate.name}
            </div>
          </div>
        </div>
      </div>

      {/* 2. EXPECTED IMPACT: FILL RATE, UNMET DEMAND, COST, RECOVERY DAY */}
      <div className="mini-kpis" style={{ marginBottom: '14px' }}>
        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Aggregate fill rate</div>
            <span className="metric-icon" aria-hidden="true">↗</span>
          </div>
          <div className="metric-value">{selectedCandidate.aggregateFillRatePct.toFixed(2)}%</div>
          <div className="metric-note">
            PROD-01: {selectedCandidate.prod1FillRatePct.toFixed(2)}% · PROD-02: {selectedCandidate.prod2FillRatePct.toFixed(2)}%
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
          <div className="metric-note">Period-level lost demand (not a backorder queue)</div>
        </article>

        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Landed procurement cost</div>
            <span className="metric-icon" aria-hidden="true">₹</span>
          </div>
          <div className="metric-value">₹{selectedCandidate.landedCostInr.toLocaleString('en-IN')}</div>
          <div className="metric-note">Evaluated landed expenditure for {selectedCandidate.name}</div>
        </article>

        <article className="panel metric">
          <div className="metric-top">
            <div className="metric-label">Recovery day</div>
            <span className="metric-icon" aria-hidden="true">◷</span>
          </div>
          <div className="metric-value">Day {selectedCandidate.recoveryDay}</div>
          <div className="metric-note">First day modeled demand is 100% fulfilled</div>
        </article>
      </div>

      {/* 3. HUMAN PLANNER REVIEW PANEL (VISIBLE HIGH IN THE VIEWPORT) */}
      <section className="panel" style={{ marginBottom: '16px', borderLeft: '4px solid var(--accent)' }}>
        <div className="panel-head">
          <div>
            <h2>Human planner review & decision sign-off</h2>
            <p>
              Selected candidate for sign-off: <strong>{selectedCandidate.name}</strong> · Decision:
              {' '}<strong style={{ textTransform: 'capitalize' }}>{plannerDecision.replace('_', ' ')}</strong>
            </p>
          </div>
          <span
            className={`status ${
              plannerDecision === 'approved'
                ? 'status-good'
                : plannerDecision === 'rejected'
                ? 'status-danger'
                : 'status-warning'
            }`}
          >
            {plannerDecision === 'approved'
              ? '✓ Approved by planner'
              : plannerDecision === 'rejected'
              ? '✕ Rejected by planner'
              : '⏳ Awaiting planner review'}
          </span>
        </div>

        <div className="panel-body">
          <div className="grid grid-2" style={{ alignItems: 'start', gap: '16px' }}>
            <div className="field">
              <label htmlFor="plannerNotes">Planner review justification & audit notes</label>
              <textarea
                id="plannerNotes"
                value={plannerReviewNotes}
                onChange={(e) => setPlannerReviewNotes(e.target.value)}
                placeholder="Record operational rationale for the selected plan..."
                style={{ minHeight: '68px' }}
              />
            </div>

            <div>
              <div style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '8px' }}>
                Decision Actions for {selectedCandidate.name}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  className={`btn ${plannerDecision === 'approved' ? 'btn-primary' : 'btn-accent'}`}
                  type="button"
                  onClick={approvePlan}
                  style={{ fontSize: '12px', padding: '8px 14px' }}
                >
                  {plannerDecision === 'approved' ? '✓ Re-Confirm Approval' : '✓ Approve Plan for Record'}
                </button>

                <button
                  className="btn"
                  type="button"
                  onClick={rejectPlan}
                  style={{
                    fontSize: '12px',
                    padding: '8px 14px',
                    color: plannerDecision === 'rejected' ? 'white' : 'var(--danger)',
                    backgroundColor: plannerDecision === 'rejected' ? 'var(--danger)' : undefined,
                    borderColor: 'var(--danger)',
                  }}
                >
                  ✕ Reject Recommendation
                </button>

                {plannerDecision !== 'awaiting_review' && (
                  <button
                    className="btn btn-quiet"
                    type="button"
                    onClick={revokePlanDecision}
                    style={{ fontSize: '12px', textDecoration: 'underline' }}
                  >
                    ↺ Reset to Awaiting Review
                  </button>
                )}
              </div>

              <div className="small muted" style={{ marginTop: '10px', lineHeight: 1.4 }}>
                <strong>Governance policy:</strong> Planner sign-off records operational authorization in the decision log.
                SupplyShield AI is a decision-support simulator; <strong>no live purchase orders are dispatched</strong> to suppliers or ERP systems.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. CANDIDATE STRATEGY COMPARISON */}
      <div style={{ marginBottom: '16px' }}>
        <div className="inline-heading">
          <div>
            <h2 style={{ margin: 0 }}>Candidate strategy comparison</h2>
            <p className="body-copy" style={{ margin: '2px 0 0' }}>
              Compare candidate allocations or switch the active plan selected for sign-off.
            </p>
          </div>
          <span className="small muted">
            Inspecting: <strong>{inspectedCandidate.name}</strong>
          </span>
        </div>

        <div className="grid grid-3" style={{ marginTop: '10px' }}>
          {candidates.map((cand) => {
            const isInspected = inspectedCandidateId === cand.id;
            const isSelectedPlan = selectedCandidateId === cand.id;
            const isRecommended = cand.id === recommendedCandidateId;
            const isInfeasible = !cand.feasible;

            let cardClass = 'candidate-card';
            if (isSelectedPlan) cardClass += ' recommended';
            if (isInfeasible) cardClass += ' infeasible';

            return (
              <article
                key={cand.id}
                className={cardClass}
                style={{
                  outline: isInspected ? '2px solid var(--info)' : undefined,
                  outlineOffset: '2px',
                }}
              >
                <div className="candidate-head">
                  <div>
                    <div className="candidate-title">{cand.name}</div>
                    <div className="candidate-subtitle">{cand.subtitle}</div>
                  </div>
                  {cand.feasible ? (
                    <span className={`status ${isRecommended ? 'status-good' : ''}`}>
                      Rank {cand.rank}
                    </span>
                  ) : (
                    <span className="status status-danger">Infeasible</span>
                  )}
                </div>

                <div className="candidate-metrics">
                  <div>
                    <span>Aggregate fill</span>
                    <strong>{cand.aggregateFillRatePct.toFixed(2)}%</strong>
                  </div>
                  <div>
                    <span>PROD-01 fill</span>
                    <strong>{cand.prod1FillRatePct.toFixed(2)}%</strong>
                  </div>
                  <div>
                    <span>Unmet demand</span>
                    <strong>{cand.unmetDemandUnits}</strong>
                  </div>
                  <div>
                    <span>Landed cost</span>
                    <strong>₹{cand.landedCostInr.toLocaleString('en-IN')}</strong>
                  </div>
                  <div>
                    <span>Recovery day</span>
                    <strong>Day {cand.recoveryDay}</strong>
                  </div>
                  <div>
                    <span>{cand.score !== null ? 'Score' : 'Selectable'}</span>
                    <strong>
                      {cand.score !== null ? cand.score.toLocaleString() : 'No (Violation)'}
                    </strong>
                  </div>
                </div>

                <p className="body-copy">{cand.rationale}</p>

                <div className="candidate-actions" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button
                    type="button"
                    className={`btn ${isInspected ? 'btn-primary' : ''}`}
                    onClick={() => handleInspect(cand.id)}
                    style={{ fontSize: '12px' }}
                  >
                    {isInspected ? '✓ Inspecting' : 'Inspect trace'}
                  </button>

                  {cand.feasible ? (
                    <button
                      type="button"
                      className={`btn ${isSelectedPlan ? 'btn-accent' : ''}`}
                      onClick={() => selectPlanForReview(cand.id)}
                      style={{ fontSize: '12px' }}
                    >
                      {isSelectedPlan ? '✓ Selected' : 'Select plan'}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn"
                      disabled
                      title="Infeasible candidates violate operational blackout constraints and cannot be selected"
                      style={{ fontSize: '11px', padding: '6px' }}
                    >
                      Cannot select
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </div>

      {/* 5. DECISION TRACE & DETAILED VALIDATION REPORT */}
      <div className="grid grid-2 section-gap">
        {/* Trace */}
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Why the plan was selected</h2>
              <p>Transparent coordinator evidence trail for {scenarioId}.</p>
            </div>
            <span className="status status-info">Decision trace</span>
          </div>

          <div className="panel-body">
            <div className="trace">
              {decisionTrace.map((event) => (
                <div key={event.step} className="trace-item">
                  <span
                    className={`trace-dot ${
                      event.status === 'good' ? 'good' : event.status === 'warning' ? 'warn' : ''
                    }`}
                  />
                  <div>
                    <strong>{event.title}</strong>
                    <p>{event.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Validation Checks */}
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Validation report: {inspectedCandidate.name}</h2>
              <p>
                {inspectedCandidate.feasible
                  ? 'All operational constraints verified.'
                  : 'Blackout violation detected — Candidate disqualified.'}
              </p>
            </div>
            <span
              className={`status ${
                inspectedCandidate.feasible ? 'status-good' : 'status-danger'
              }`}
            >
              {inspectedCandidate.feasible ? 'Status: Valid' : 'Status: Infeasible'}
            </span>
          </div>

          <div className="panel-body">
            <div className="check-list">
              {validationChecks.map((check) => {
                const isReorderBlackout =
                  inspectedCandidate.id === 'reorder' && check.id === 'CHK-02';

                const status = isReorderBlackout ? 'FAIL' : check.status;
                const isPass = status === 'PASS';
                const isLimit = status === 'NOT_MODELED';

                return (
                  <div key={check.id} className="check-row">
                    <span
                      className={`check-icon ${
                        isPass ? 'check-pass' : isLimit ? 'check-limit' : 'check-fail'
                      }`}
                    >
                      {isPass ? '✓' : isLimit ? 'i' : '✗'}
                    </span>
                    <div>
                      <strong>{check.name}</strong>
                      <p>
                        {isReorderBlackout
                          ? 'Orders attempted with SUP-01 during blackout window violate operational constraint.'
                          : check.description}
                      </p>
                      <small className="muted" style={{ display: 'block', marginTop: '4px' }}>
                        {isReorderBlackout
                          ? 'Reorder strategy issues orders on blackout days, triggering rejection.'
                          : check.detail}
                      </small>
                    </div>
                    <span
                      className={`status ${
                        isPass ? 'status-good' : isLimit ? 'status-info' : 'status-danger'
                      }`}
                    >
                      {status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </div>

      <div className="footnote">
        <span>
          Selected plan: <strong>{selectedCandidate.name}</strong> ({plannerDecision.replace('_', ' ')})
        </span>
        <span>
          External execution: <strong>False</strong> · No purchase orders dispatched
        </span>
      </div>
    </section>
  );
};
