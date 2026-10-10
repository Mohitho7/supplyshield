import React from 'react';
import { useScenario } from '../../context/useScenario';

const PAGE_TITLES: Record<string, string> = {
  command: 'Command center',
  scenario: 'Scenario lab',
  network: 'Supply network',
  sourcing: 'Supplier capacity',
  recovery: 'Recovery workspace',
  benchmark: 'Strategy benchmark',
};

export const TopBar: React.FC = () => {
  const {
    page,
    scenarioId,
    scenarioData,
    backendLive,
    plannerDecision,
    selectedCandidateId,
    candidates,
    toggleTheme,
    checkBackendStatus,
    isLoading,
    dataStatus,
  } = useScenario();

  const selectedCandidate =
    candidates.find((c) => c.id === selectedCandidateId) || candidates[0];

  return (
    <header className="topbar">
      <div className="crumb">
        Operations <span aria-hidden="true">/</span>{' '}
        <strong>{PAGE_TITLES[page] || 'Dashboard'}</strong>
      </div>

      <div className="top-actions">
        {backendLive ? (
          <span className="prototype-flag live" title="Direct API connection active">
            <span className="dot" />
            LIVE BACKEND CONNECTED
          </span>
        ) : (
          <span
            className="prototype-flag"
            title={
              scenarioData.isVerifiedSnapshot
                ? 'Backend offline. Displaying verified reference snapshot from project documentation.'
                : 'Backend offline. Displaying interpolated demo estimate.'
            }
          >
            <span className="dot" />
            DEMO REFERENCE DATA
            {scenarioData.isVerifiedSnapshot ? ' · VERIFIED' : ' · ESTIMATE'}
          </span>
        )}

        {dataStatus && (
          <span
            className="status status-info"
            style={{ fontSize: '11px', padding: '4px 8px', fontWeight: 600 }}
            title={`Active dataset ${dataStatus.datasetId} (v${dataStatus.datasetVersion}) · Fingerprint: ${dataStatus.datasetFingerprint}`}
          >
            DATA: {dataStatus.datasetId} · {dataStatus.validationStatus}
          </span>
        )}

        <span className="scenario-pill" id="scenarioBadge" title="Active deterministic scenario reference">
          {scenarioId}
        </span>

        {/* Compact, accurate planner decision status */}
        {plannerDecision === 'approved' && (
          <span
            className="status status-good"
            style={{ fontSize: '11px', fontWeight: 800 }}
            title={`Planner has approved ${selectedCandidate.name}. Live PO execution disabled.`}
          >
            ✓ Approved: {selectedCandidate.name}
          </span>
        )}
        {plannerDecision === 'rejected' && (
          <span
            className="status status-danger"
            style={{ fontSize: '11px', fontWeight: 800 }}
            title={`Planner has marked ${selectedCandidate.name} as rejected.`}
          >
            ✕ Rejected: {selectedCandidate.name}
          </span>
        )}
        {plannerDecision === 'awaiting_review' && (
          <span
            className="status status-warning"
            style={{ fontSize: '11px', fontWeight: 800 }}
            title={`No approval recorded yet. ${selectedCandidate.name} is awaiting planner review.`}
          >
            ⏳ Awaiting review
          </span>
        )}

        <button
          className="btn"
          type="button"
          onClick={() => checkBackendStatus()}
          disabled={isLoading}
          aria-label="Recheck FastAPI backend status"
          title="Verify connection to http://127.0.0.1:8000"
          style={{ fontSize: '12px', padding: '6px 10px', minHeight: '34px' }}
        >
          {isLoading ? 'Checking...' : '↻ API Check'}
        </button>

        <button
          className="btn"
          id="themeToggle"
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle light and dark preview"
          style={{ fontSize: '12px', padding: '6px 12px', minHeight: '34px' }}
        >
          ◐ Theme
        </button>
      </div>
    </header>
  );
};
