import { createContext } from 'react';
import type {
  CandidateId,
  CandidateMetrics,
  DataStatus,
  DecisionTraceEvent,
  NetworkNodeData,
  NodeId,
  PageId,
  PlannerDecision,
  ScenarioImpact,
  ValidationCheck,
} from '../types';

export interface ScenarioContextType {
  page: PageId;
  setPage: (p: PageId) => void;
  shutdownDays: number;
  setShutdownDays: (days: number) => void;
  horizonDays: number;
  seed: number;
  scenarioId: string;
  scenarioData: ScenarioImpact;
  candidates: CandidateMetrics[];
  validationChecks: ValidationCheck[];
  decisionTrace: DecisionTraceEvent[];
  networkNodes: Record<NodeId, NetworkNodeData>;
  selectedNodeId: NodeId;
  setSelectedNodeId: (id: NodeId) => void;
  recommendedCandidateId: CandidateId;
  inspectedCandidateId: CandidateId;
  setInspectedCandidateId: (id: CandidateId) => void;
  selectedCandidateId: CandidateId;
  selectPlanForReview: (id: CandidateId) => void;
  plannerDecision: PlannerDecision;
  approvePlan: () => void;
  rejectPlan: () => void;
  revokePlanDecision: () => void;
  plannerApproved: boolean;
  togglePlannerApproval: () => void;
  plannerReviewNotes: string;
  setPlannerReviewNotes: (notes: string) => void;
  theme: 'light' | 'dark';
  toggleTheme: () => void;
  backendLive: boolean;
  backendStatusMessage: string;
  checkBackendStatus: () => Promise<void>;
  toastMessage: string | null;
  showToast: (msg: string) => void;
  isLoading: boolean;
  apiError: string | null;
  dataStatus: DataStatus | null;
}

export const ScenarioContext = createContext<ScenarioContextType | undefined>(undefined);
