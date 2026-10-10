import React, { useCallback, useEffect, useState } from 'react';
import {
  api,
  getCandidatesForScenario,
  getDecisionTrace,
  getNetworkNodes,
  getScenarioSnapshot,
  getValidationChecks,
} from '../api/client';
import type {
  CandidateId,
  CandidateMetrics,
  DecisionTraceEvent,
  NetworkNodeData,
  NodeId,
  PageId,
  PlannerDecision,
  ScenarioImpact,
  ValidationCheck,
} from '../types';
import { ScenarioContext } from './ScenarioContextDefinition';

export const ScenarioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [page, setPage] = useState<PageId>('command');
  const [shutdownDays, setShutdownDaysState] = useState<number>(7);
  const [selectedNodeId, setSelectedNodeId] = useState<NodeId>('SUP-01');

  // Distinct recovery governance states
  const recommendedCandidateId: CandidateId = 'agent';
  const [inspectedCandidateId, setInspectedCandidateId] = useState<CandidateId>('agent');
  const [selectedCandidateId, setSelectedCandidateId] = useState<CandidateId>('agent');
  const [plannerDecision, setPlannerDecision] = useState<PlannerDecision>('awaiting_review');
  const [plannerReviewNotes, setPlannerReviewNotes] = useState<string>(
    'Priority allocation to PROD-01 verified against critical customer contracts.'
  );

  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [backendLive, setBackendLive] = useState<boolean>(false);
  const [backendStatusMessage, setBackendStatusMessage] = useState<string>('Offline · Serving Reference Data');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const [scenarioData, setScenarioData] = useState<ScenarioImpact>(() => getScenarioSnapshot(7));
  const [candidates, setCandidates] = useState<CandidateMetrics[]>(() => getCandidatesForScenario(7));
  const [validationChecks, setValidationChecks] = useState<ValidationCheck[]>(() => getValidationChecks());
  const [decisionTrace, setDecisionTrace] = useState<DecisionTraceEvent[]>(() =>
    getDecisionTrace('SCEN-SD7-H21-S42')
  );
  const [networkNodes, setNetworkNodes] = useState<Record<NodeId, NetworkNodeData>>(() => getNetworkNodes(7));

  const horizonDays = 21;
  const seed = 42;
  const scenarioId = `SCEN-SD${shutdownDays}-H21-S42`;
  const plannerApproved = plannerDecision === 'approved';

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
  }, []);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => {
      setToastMessage(null);
    }, 4000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const nextTheme = prev === 'light' ? 'dark' : 'light';
      document.documentElement.dataset.theme = nextTheme;
      return nextTheme;
    });
  }, []);

  const checkBackendStatus = useCallback(async () => {
    try {
      const res = await api.checkHealth();
      setBackendLive(res.online);
      setBackendStatusMessage(res.message);
      if (!res.online) {
        setApiError(null);
      }
    } catch {
      setBackendLive(false);
      setBackendStatusMessage('Offline');
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    api.checkHealth().then((res) => {
      if (!ignore) {
        setBackendLive(res.online);
        setBackendStatusMessage(res.message);
      }
    }).catch(() => {
      if (!ignore) {
        setBackendLive(false);
        setBackendStatusMessage('Offline');
      }
    });
    return () => {
      ignore = true;
    };
  }, []);

  const setShutdownDays = useCallback(async (days: number) => {
    const sanitized = Math.max(1, Math.min(14, days));
    setShutdownDaysState(sanitized);
    setIsLoading(true);
    setApiError(null);

    try {
      if (backendLive) {
        const [simRes, recRes, netRes] = await Promise.all([
          api.getSimulation(sanitized, 'agent'),
          api.getRecovery(sanitized),
          api.getNetwork(sanitized),
        ]);

        setScenarioData(simRes.data);
        setCandidates(recRes.candidates);
        setValidationChecks(recRes.checks);
        setDecisionTrace(recRes.trace);
        setNetworkNodes(netRes.data);
        showToast(`Calculated live scenario for ${sanitized}-day shutdown.`);
      } else {
        const sim = getScenarioSnapshot(sanitized);
        const cands = getCandidatesForScenario(sanitized);
        const checks = getValidationChecks();
        const trace = getDecisionTrace(sim.scenarioId);
        const nodes = getNetworkNodes(sanitized);

        setScenarioData(sim);
        setCandidates(cands);
        setValidationChecks(checks);
        setDecisionTrace(trace);
        setNetworkNodes(nodes);

        if (sim.isVerifiedSnapshot) {
          showToast(`Loaded verified ${sanitized}-day reference scenario (${sim.scenarioId}).`);
        } else {
          showToast(`Loaded ${sanitized}-day demo estimate (${sim.scenarioId}). Connect backend for verified results.`);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to calculate scenario';
      setApiError(msg);
      showToast(`Error: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  }, [backendLive, showToast]);

  const selectPlanForReview = useCallback((id: CandidateId) => {
    if (id === 'reorder') {
      showToast('The reorder baseline violates the shutdown blackout rule and is never selectable.');
      return;
    }
    const candName = id === 'agent' ? 'Agent-assisted' : 'OR-Tools optimized';
    setSelectedCandidateId(id);
    setInspectedCandidateId(id);
    setPlannerDecision('awaiting_review');
    showToast(`Selected ${candName} for planner review. Status set to Awaiting review.`);
  }, [showToast]);

  const approvePlan = useCallback(() => {
    if (selectedCandidateId === 'reorder') {
      showToast('Cannot approve an infeasible plan.');
      return;
    }
    const candName = selectedCandidateId === 'agent' ? 'Agent-assisted' : 'OR-Tools optimized';
    setPlannerDecision('approved');
    showToast(`${candName} approved by planner. Note: External purchase execution is disabled.`);
  }, [selectedCandidateId, showToast]);

  const rejectPlan = useCallback(() => {
    const candName = selectedCandidateId === 'agent' ? 'Agent-assisted' : 'OR-Tools optimized';
    setPlannerDecision('rejected');
    showToast(`${candName} marked as rejected by planner.`);
  }, [selectedCandidateId, showToast]);

  const revokePlanDecision = useCallback(() => {
    const candName = selectedCandidateId === 'agent' ? 'Agent-assisted' : 'OR-Tools optimized';
    setPlannerDecision('awaiting_review');
    showToast(`Decision reset. ${candName} is awaiting review.`);
  }, [selectedCandidateId, showToast]);

  const togglePlannerApproval = useCallback(() => {
    if (plannerDecision === 'approved') {
      revokePlanDecision();
    } else {
      approvePlan();
    }
  }, [plannerDecision, approvePlan, revokePlanDecision]);

  return (
    <ScenarioContext.Provider
      value={{
        page,
        setPage,
        shutdownDays,
        setShutdownDays,
        horizonDays,
        seed,
        scenarioId,
        scenarioData,
        candidates,
        validationChecks,
        decisionTrace,
        networkNodes,
        selectedNodeId,
        setSelectedNodeId,
        recommendedCandidateId,
        inspectedCandidateId,
        setInspectedCandidateId,
        selectedCandidateId,
        selectPlanForReview,
        plannerDecision,
        approvePlan,
        rejectPlan,
        revokePlanDecision,
        plannerApproved,
        togglePlannerApproval,
        plannerReviewNotes,
        setPlannerReviewNotes,
        theme,
        toggleTheme,
        backendLive,
        backendStatusMessage,
        checkBackendStatus,
        toastMessage,
        showToast,
        isLoading,
        apiError,
      }}
    >
      {children}
    </ScenarioContext.Provider>
  );
};
