export type PageId = 'command' | 'scenario' | 'network' | 'sourcing' | 'recovery' | 'benchmark';

export type CandidateId = 'agent' | 'optimized' | 'reorder';

export type PlannerDecision = 'awaiting_review' | 'approved' | 'rejected';

export type NodeId = 'SUP-01' | 'SUP-02' | 'FAC-01' | 'FAC-02' | 'DC-01' | 'DC-02';

export interface ProductService {
  fulfilled: number;
  demand: number;
  fillRatePct: number;
  unmet: number;
}

export interface ScenarioImpact {
  scenarioId: string;
  shutdownDays: number;
  horizonDays: number;
  seed: number;
  aggregateFillRatePct: number;
  unmetDemandUnits: number;
  landedCostInr: number;
  recoveryDay: number;
  typeLabel: string;
  isVerifiedSnapshot: boolean;
  products: {
    'PROD-01': ProductService;
    'PROD-02': ProductService;
  };
}

export interface CandidateMetrics {
  id: CandidateId;
  name: string;
  subtitle: string;
  feasible: boolean;
  selectable: boolean;
  rank: number | null;
  rankLabel: string;
  aggregateFillRatePct: number;
  prod1FillRatePct: number;
  prod1Fulfilled: number;
  prod1Demand: number;
  prod2FillRatePct: number;
  prod2Fulfilled: number;
  prod2Demand: number;
  unmetDemandUnits: number;
  landedCostInr: number;
  recoveryDay: number;
  score: number | null;
  rationale: string;
  isVerified: boolean;
}

export interface ValidationCheck {
  id: string;
  name: string;
  description: string;
  status: 'PASS' | 'FAIL' | 'NOT_MODELED';
  detail: string;
}

export interface DecisionTraceEvent {
  step: number;
  title: string;
  detail: string;
  status: 'info' | 'good' | 'warning';
}

export interface NetworkNodeData {
  id: NodeId;
  type: 'Supplier' | 'Factory' | 'Distribution Center';
  name: string;
  role: string;
  status: string;
  statusClass: 'status-danger' | 'status-warning' | 'status-good' | 'status-info';
  description: string;
  attributes: [string, string][];
}

export interface DataStatus {
  datasetId: string;
  datasetVersion: string;
  datasetFingerprint: string;
  sourceType: string;
  isSynthetic: boolean;
  loadStatus: string;
  validationStatus: string;
  supplierCount: number;
  productCount: number;
  nodeCount: number;
  summary: string;
}
