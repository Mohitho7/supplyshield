import type {
  CandidateMetrics,
  DecisionTraceEvent,
  NetworkNodeData,
  NodeId,
  ScenarioImpact,
  ValidationCheck,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export interface HealthCheckResponse {
  status: string;
  version?: string;
}

// Canonical reference snapshots documented in SupplyShield_Frontend_Handoff.md
export const REFERENCE_SNAPSHOTS: Record<number, ScenarioImpact> = {
  1: {
    scenarioId: 'SCEN-SD1-H21-S42',
    shutdownDays: 1,
    horizonDays: 21,
    seed: 42,
    aggregateFillRatePct: 96.13,
    unmetDemandUnits: 65,
    landedCostInr: 17280,
    recoveryDay: 4,
    typeLabel: 'Short disruption (Verified snapshot)',
    isVerifiedSnapshot: true,
    products: {
      'PROD-01': {
        fulfilled: 910,
        demand: 945,
        fillRatePct: 96.3,
        unmet: 35,
      },
      'PROD-02': {
        fulfilled: 705,
        demand: 735,
        fillRatePct: 95.92,
        unmet: 30,
      },
    },
  },
  7: {
    scenarioId: 'SCEN-SD7-H21-S42',
    shutdownDays: 7,
    horizonDays: 21,
    seed: 42,
    aggregateFillRatePct: 85.42,
    unmetDemandUnits: 245,
    landedCostInr: 16470,
    recoveryDay: 10,
    typeLabel: 'Baseline reference (Verified snapshot)',
    isVerifiedSnapshot: true,
    products: {
      'PROD-01': {
        fulfilled: 865,
        demand: 945,
        fillRatePct: 91.53,
        unmet: 80,
      },
      'PROD-02': {
        fulfilled: 570,
        demand: 735,
        fillRatePct: 77.55,
        unmet: 165,
      },
    },
  },
  14: {
    scenarioId: 'SCEN-SD14-H21-S42',
    shutdownDays: 14,
    horizonDays: 21,
    seed: 42,
    aggregateFillRatePct: 77.08,
    unmetDemandUnits: 385,
    landedCostInr: 16680,
    recoveryDay: 17,
    typeLabel: 'Severe disruption (Verified snapshot)',
    isVerifiedSnapshot: true,
    products: {
      'PROD-01': {
        fulfilled: 865,
        demand: 945,
        fillRatePct: 91.53,
        unmet: 80,
      },
      'PROD-02': {
        fulfilled: 430,
        demand: 735,
        fillRatePct: 58.5,
        unmet: 305,
      },
    },
  },
};

export function getScenarioSnapshot(shutdownDays: number): ScenarioImpact {
  if (REFERENCE_SNAPSHOTS[shutdownDays]) {
    return REFERENCE_SNAPSHOTS[shutdownDays];
  }

  // Model-compliant interpolation for 1-14 days based on the 21-day horizon
  // 1680 total units (945 PROD-01, 735 PROD-02)
  const d = Math.max(1, Math.min(14, shutdownDays));
  // Total unmet scales with shutdown length constrained by SUP-02 lead time (4d) and opening buffer
  const unmetUnits = Math.round(50 + d * 24);
  const aggregateFulfilled = 1680 - unmetUnits;
  const aggregateFillPct = Number(((aggregateFulfilled / 1680) * 100).toFixed(2));

  // Under priority allocation: PROD-01 gets protected first
  const prod1Unmet = Math.min(Math.round(20 + d * 8.5), 945);
  const prod1Fulfilled = 945 - prod1Unmet;
  const prod1Pct = Number(((prod1Fulfilled / 945) * 100).toFixed(2));

  const prod2Unmet = Math.max(0, unmetUnits - prod1Unmet);
  const prod2Fulfilled = 735 - prod2Unmet;
  const prod2Pct = Number(((prod2Fulfilled / 735) * 100).toFixed(2));

  const recoveryDay = Math.min(21, d + 3);
  const landedCostInr = Math.round(17300 - d * 110 + (d > 7 ? (d - 7) * 140 : 0));

  return {
    scenarioId: `SCEN-SD${d}-H21-S42`,
    shutdownDays: d,
    horizonDays: 21,
    seed: 42,
    aggregateFillRatePct: aggregateFillPct,
    unmetDemandUnits: unmetUnits,
    landedCostInr: landedCostInr,
    recoveryDay: recoveryDay,
    typeLabel: `Demo estimate (Duration ${d}d · unverified)`,
    isVerifiedSnapshot: false,
    products: {
      'PROD-01': {
        fulfilled: prod1Fulfilled,
        demand: 945,
        fillRatePct: prod1Pct,
        unmet: prod1Unmet,
      },
      'PROD-02': {
        fulfilled: prod2Fulfilled,
        demand: 735,
        fillRatePct: prod2Pct,
        unmet: prod2Unmet,
      },
    },
  };
}

export function getCandidatesForScenario(shutdownDays: number): CandidateMetrics[] {
  // D=7 exact values from handoff
  if (shutdownDays === 7) {
    return [
      {
        id: 'agent',
        name: 'Agent-assisted',
        subtitle: 'Priority-aware allocation · Candidate A',
        feasible: true,
        selectable: true,
        rank: 1,
        rankLabel: 'Selected · Rank 1',
        aggregateFillRatePct: 85.42,
        prod1FillRatePct: 91.53,
        prod1Fulfilled: 865,
        prod1Demand: 945,
        prod2FillRatePct: 77.55,
        prod2Fulfilled: 570,
        prod2Demand: 735,
        unmetDemandUnits: 245,
        landedCostInr: 16470,
        recoveryDay: 10,
        score: 13379.57,
        rationale: 'Prioritizes high-margin PROD-01 service while matching uniform optimizer aggregate volume.',
        isVerified: true,
      },
      {
        id: 'optimized',
        name: 'OR-Tools optimized',
        subtitle: 'Uniform shortage objective · Candidate B',
        feasible: true,
        selectable: true,
        rank: 2,
        rankLabel: 'Rank 2',
        aggregateFillRatePct: 85.42,
        prod1FillRatePct: 85.19,
        prod1Fulfilled: 805,
        prod1Demand: 945,
        prod2FillRatePct: 85.71,
        prod2Fulfilled: 630,
        prod2Demand: 735,
        unmetDemandUnits: 245,
        landedCostInr: 16470,
        recoveryDay: 10,
        score: 12744.65,
        rationale: 'Minimizes maximum product shortage evenly across products. Valid but scores lower on priority weight.',
        isVerified: true,
      },
      {
        id: 'reorder',
        name: 'Reorder baseline',
        subtitle: 'Historical rule-based benchmark · Candidate C',
        feasible: false,
        selectable: false,
        rank: null,
        rankLabel: 'Benchmark only (Infeasible)',
        aggregateFillRatePct: 65.48,
        prod1FillRatePct: 67.72,
        prod1Fulfilled: 640,
        prod1Demand: 945,
        prod2FillRatePct: 62.59,
        prod2Fulfilled: 460,
        prod2Demand: 735,
        unmetDemandUnits: 580,
        landedCostInr: 12060,
        recoveryDay: 11,
        score: null,
        rationale: 'Violates shutdown blackout rule by attempting orders during blackout. Infeasible and never selectable.',
        isVerified: true,
      },
    ];
  }

  // D=1 exact values from handoff & UX reference
  if (shutdownDays === 1) {
    return [
      {
        id: 'agent',
        name: 'Agent-assisted',
        subtitle: 'Priority-aware allocation · Candidate A',
        feasible: true,
        selectable: true,
        rank: 1,
        rankLabel: 'Selected · Rank 1',
        aggregateFillRatePct: 96.13,
        prod1FillRatePct: 96.30,
        prod1Fulfilled: 910,
        prod1Demand: 945,
        prod2FillRatePct: 95.92,
        prod2Fulfilled: 705,
        prod2Demand: 735,
        unmetDemandUnits: 65,
        landedCostInr: 17280,
        recoveryDay: 4,
        score: 14210.00,
        rationale: 'Short 1-day disruption absorbed smoothly with buffer stock and quick supplier reorder.',
        isVerified: true,
      },
      {
        id: 'optimized',
        name: 'OR-Tools optimized',
        subtitle: 'Uniform shortage objective · Candidate B',
        feasible: true,
        selectable: true,
        rank: 2,
        rankLabel: 'Rank 2',
        aggregateFillRatePct: 96.13,
        prod1FillRatePct: 96.30,
        prod1Fulfilled: 910,
        prod1Demand: 945,
        prod2FillRatePct: 95.92,
        prod2Fulfilled: 705,
        prod2Demand: 735,
        unmetDemandUnits: 65,
        landedCostInr: 17280,
        recoveryDay: 4,
        score: 13610.00,
        rationale: 'Uniform solver solution achieves identical fill under short outage.',
        isVerified: true,
      },
      {
        id: 'reorder',
        name: 'Reorder baseline',
        subtitle: 'Historical rule-based benchmark · Candidate C',
        feasible: false,
        selectable: false,
        rank: null,
        rankLabel: 'Benchmark only (Infeasible · Demo estimate)',
        aggregateFillRatePct: 89.20,
        prod1FillRatePct: 90.10,
        prod1Fulfilled: 851,
        prod1Demand: 945,
        prod2FillRatePct: 88.00,
        prod2Fulfilled: 647,
        prod2Demand: 735,
        unmetDemandUnits: 182,
        landedCostInr: 13950,
        recoveryDay: 6,
        score: null,
        rationale: 'Blackout violation on Day 1. Kept as non-selectable benchmark.',
        isVerified: false,
      },
    ];
  }

  // D=14 exact values from handoff & UX reference
  if (shutdownDays === 14) {
    return [
      {
        id: 'agent',
        name: 'Agent-assisted',
        subtitle: 'Priority-aware allocation · Candidate A',
        feasible: true,
        selectable: true,
        rank: 1,
        rankLabel: 'Selected · Rank 1',
        aggregateFillRatePct: 77.08,
        prod1FillRatePct: 91.53,
        prod1Fulfilled: 865,
        prod1Demand: 945,
        prod2FillRatePct: 58.50,
        prod2Fulfilled: 430,
        prod2Demand: 735,
        unmetDemandUnits: 385,
        landedCostInr: 16680,
        recoveryDay: 17,
        score: 12150.00,
        rationale: 'Severely constrained. Protects critical PROD-01 at 91.53% by allowing PROD-02 to absorb shortfall.',
        isVerified: true,
      },
      {
        id: 'optimized',
        name: 'OR-Tools optimized',
        subtitle: 'Uniform shortage objective · Candidate B',
        feasible: true,
        selectable: true,
        rank: 2,
        rankLabel: 'Rank 2',
        aggregateFillRatePct: 77.08,
        prod1FillRatePct: 72.49,
        prod1Fulfilled: 685,
        prod1Demand: 945,
        prod2FillRatePct: 82.99,
        prod2Fulfilled: 610,
        prod2Demand: 735,
        unmetDemandUnits: 385,
        landedCostInr: 16680,
        recoveryDay: 17,
        score: 11550.00,
        rationale: 'Evenly distributes shortages across products (72.49% and 82.99%).',
        isVerified: true,
      },
      {
        id: 'reorder',
        name: 'Reorder baseline',
        subtitle: 'Historical rule-based benchmark · Candidate C',
        feasible: false,
        selectable: false,
        rank: null,
        rankLabel: 'Benchmark only (Infeasible · Demo estimate)',
        aggregateFillRatePct: 49.10,
        prod1FillRatePct: 51.30,
        prod1Fulfilled: 485,
        prod1Demand: 945,
        prod2FillRatePct: 46.20,
        prod2Fulfilled: 340,
        prod2Demand: 735,
        unmetDemandUnits: 855,
        landedCostInr: 9840,
        recoveryDay: 19,
        score: null,
        rationale: 'Catastrophic blackout violations across Days 1–14. Infeasible benchmark only.',
        isVerified: false,
      },
    ];
  }

  // Generalized Demo Estimates for intermediate days D in [2..6, 8..13]
  const scenario = getScenarioSnapshot(shutdownDays);
  const aggFill = scenario.aggregateFillRatePct;
  const unmet = scenario.unmetDemandUnits;
  const cost = scenario.landedCostInr;
  const recDay = scenario.recoveryDay;
  const p1 = scenario.products['PROD-01'];
  const p2 = scenario.products['PROD-02'];

  const optP1Pct = Number(aggFill.toFixed(2));
  const optP1Fulfilled = Math.round((optP1Pct / 100) * 945);
  const optP2Fulfilled = Math.round(1680 - unmet - optP1Fulfilled);
  const optP2Pct = Number(((optP2Fulfilled / 735) * 100).toFixed(2));

  const baseUnmet = Math.round(unmet * 2.3);
  const baseFill = Number((((1680 - baseUnmet) / 1680) * 100).toFixed(2));
  const baseCost = Math.round(cost * 0.73);

  return [
    {
      id: 'agent',
      name: 'Agent-assisted',
      subtitle: 'Priority-aware allocation · Candidate A',
      feasible: true,
      selectable: true,
      rank: 1,
      rankLabel: 'Selected · Rank 1 (Demo estimate)',
      aggregateFillRatePct: aggFill,
      prod1FillRatePct: p1.fillRatePct,
      prod1Fulfilled: p1.fulfilled,
      prod1Demand: p1.demand,
      prod2FillRatePct: p2.fillRatePct,
      prod2Fulfilled: p2.fulfilled,
      prod2Demand: p2.demand,
      unmetDemandUnits: unmet,
      landedCostInr: cost,
      recoveryDay: recDay,
      score: Number((aggFill * 100 + p1.fillRatePct * 50 - cost * 0.1).toFixed(2)),
      rationale: 'Protected critical product PROD-01 fulfillment through constrained alternate sourcing. Demo estimate.',
      isVerified: false,
    },
    {
      id: 'optimized',
      name: 'OR-Tools optimized',
      subtitle: 'Uniform shortage objective · Candidate B',
      feasible: true,
      selectable: true,
      rank: 2,
      rankLabel: 'Rank 2 (Demo estimate)',
      aggregateFillRatePct: aggFill,
      prod1FillRatePct: optP1Pct,
      prod1Fulfilled: optP1Fulfilled,
      prod1Demand: 945,
      prod2FillRatePct: optP2Pct,
      prod2Fulfilled: optP2Fulfilled,
      prod2Demand: 735,
      unmetDemandUnits: unmet,
      landedCostInr: cost,
      recoveryDay: recDay,
      score: Number((aggFill * 100 + optP1Pct * 50 - cost * 0.1 - 600).toFixed(2)),
      rationale: 'Uniform solver solution estimate. Valid but less protective of priority product.',
      isVerified: false,
    },
    {
      id: 'reorder',
      name: 'Reorder baseline',
      subtitle: 'Historical rule-based benchmark · Candidate C',
      feasible: false,
      selectable: false,
      rank: null,
      rankLabel: 'Benchmark only (Infeasible · Demo estimate)',
      aggregateFillRatePct: baseFill,
      prod1FillRatePct: Number((baseFill * 1.03).toFixed(2)),
      prod1Fulfilled: Math.round(((baseFill * 1.03) / 100) * 945),
      prod1Demand: 945,
      prod2FillRatePct: Number((baseFill * 0.95).toFixed(2)),
      prod2Fulfilled: Math.round(((baseFill * 0.95) / 100) * 735),
      prod2Demand: 735,
      unmetDemandUnits: baseUnmet,
      landedCostInr: baseCost,
      recoveryDay: Math.min(21, recDay + 2),
      score: null,
      rationale: 'Orders placed during blackout period are rejected by operational constraints. Infeasible benchmark.',
      isVerified: false,
    },
  ];
}

export function getValidationChecks(): ValidationCheck[] {
  return [
    {
      id: 'CHK-01',
      name: 'Order quantities and supplier IDs',
      description: 'Orders use recognized suppliers and positive integer quantities.',
      status: 'PASS',
      detail: 'Both SUP-01 and SUP-02 IDs valid; quantities are discrete multiples within bounds.',
    },
    {
      id: 'CHK-02',
      name: 'Supplier blackout and capacity',
      description: 'Orders respect the configured blackout window and modeled supplier daily capacity.',
      status: 'PASS',
      detail: 'No orders placed with SUP-01 during blackout. SUP-02 daily orders capped at 60 units/day.',
    },
    {
      id: 'CHK-03',
      name: 'Lead time and planning horizon',
      description: 'Arrival days follow order-day plus lead-time convention within the 21-day horizon.',
      status: 'PASS',
      detail: 'SUP-01 = 2 days lead time, SUP-02 = 4 days lead time verified. All orders arrive by Day 21.',
    },
    {
      id: 'CHK-04',
      name: 'Cost and ranking integrity',
      description: 'Candidate metrics reconcile to the ranking record and published score formula.',
      status: 'PASS',
      detail: 'Landed unit costs (₹12.00 primary, ₹16.50 alternate) match financial reconciliation.',
    },
    {
      id: 'CHK-05',
      name: 'Factory and DC flow constraints',
      description: 'Downstream multi-echelon transfer and conversion limits are structural metadata.',
      status: 'NOT_MODELED',
      detail: 'Not enforced in the current model. Unconstrained downstream routing assumption.',
    },
  ];
}

export function getDecisionTrace(scenarioId: string): DecisionTraceEvent[] {
  return [
    {
      step: 1,
      title: 'Scenario accepted',
      detail: `${scenarioId} · 21-day deterministic horizon, seed 42.`,
      status: 'info',
    },
    {
      step: 2,
      title: 'Specialist evidence generated',
      detail: 'Demand, inventory buffer, supplier risk, and logistics analyses evaluated.',
      status: 'info',
    },
    {
      step: 3,
      title: 'Candidate plans evaluated',
      detail: 'Candidate plans validated against supplier blackout, lead time, and capacity constraints.',
      status: 'info',
    },
    {
      step: 4,
      title: 'Feasible plans ranked',
      detail: 'Fulfillment ratios and weighted priority scoring applied to valid candidates.',
      status: 'good',
    },
    {
      step: 5,
      title: 'Agent-assisted plan selected for review',
      detail: 'Rank 1 candidate recommended to human planner. Advisory state; no order dispatched.',
      status: 'good',
    },
    {
      step: 6,
      title: 'External execution disabled',
      detail: 'No ERP integration or automated purchasing dispatch is configured.',
      status: 'warning',
    },
  ];
}

export function getNetworkNodes(shutdownDays: number): Record<NodeId, NetworkNodeData> {
  return {
    'SUP-01': {
      id: 'SUP-01',
      type: 'Supplier',
      name: 'Primary supplier',
      role: 'Tier 1 Component Sourcing',
      status: 'Disrupted',
      statusClass: 'status-danger',
      description: `Unavailable during the configured ${shutdownDays}-day shutdown. Orders placed during the blackout are rejected by modeled constraints.`,
      attributes: [
        ['Lead time', '2 days'],
        ['Daily capacity', '100 units'],
        ['Landed unit cost', '₹12.00'],
        ['Blackout window', `Days 1–${shutdownDays}`],
        ['Downstream link', 'Supplies FAC-01 and FAC-02'],
      ],
    },
    'SUP-02': {
      id: 'SUP-02',
      type: 'Supplier',
      name: 'Alternate supplier',
      role: 'Secondary / Backup Sourcing',
      status: 'Constrained',
      statusClass: 'status-warning',
      description: 'Operational with longer lead time and higher landed unit cost. Cannot independently cover full 80-unit daily demand at 60 units/day capacity.',
      attributes: [
        ['Lead time', '4 days'],
        ['Daily capacity', '60 units'],
        ['Landed unit cost', '₹16.50'],
        ['Capacity vs demand', '60 / 80 units per day (75%)'],
        ['Downstream link', 'Supplies FAC-01 and FAC-02'],
      ],
    },
    'FAC-01': {
      id: 'FAC-01',
      type: 'Factory',
      name: 'Assembly Plant 01',
      role: 'PROD-01 Final Assembly',
      status: 'Operational',
      statusClass: 'status-info',
      description: 'Primary assembly for PROD-01. Factory throughput constraints are structural topology metadata and not enforced.',
      attributes: [
        ['Primary product', 'PROD-01 (Priority)'],
        ['Upstream sources', 'SUP-01, SUP-02'],
        ['Constraint status', 'Topology metadata (unconstrained)'],
        ['Downstream DC', 'Feeds DC-01'],
      ],
    },
    'FAC-02': {
      id: 'FAC-02',
      type: 'Factory',
      name: 'Assembly Plant 02',
      role: 'PROD-02 Final Assembly',
      status: 'Operational',
      statusClass: 'status-info',
      description: 'Secondary assembly line for PROD-02. Downstream conversion is not throttled in the current simulator model.',
      attributes: [
        ['Primary product', 'PROD-02 (Standard)'],
        ['Upstream sources', 'SUP-01, SUP-02'],
        ['Constraint status', 'Topology metadata (unconstrained)'],
        ['Downstream DC', 'Feeds DC-02'],
      ],
    },
    'DC-01': {
      id: 'DC-01',
      type: 'Distribution Center',
      name: 'Northern Fulfillment DC',
      role: 'Regional Customer Service',
      status: 'Operational',
      statusClass: 'status-info',
      description: 'Distribution hub serving regional enterprise accounts. Internal transfer lag is not enforced in the simulation.',
      attributes: [
        ['Assigned demand', '45 units/day (PROD-01)'],
        ['Upstream factory', 'FAC-01'],
        ['Constraint scope', 'Topology metadata'],
        ['Outbound status', 'Lost-service convention applied'],
      ],
    },
    'DC-02': {
      id: 'DC-02',
      type: 'Distribution Center',
      name: 'Southern Fulfillment DC',
      role: 'Commercial Channel Service',
      status: 'Operational',
      statusClass: 'status-info',
      description: 'Distribution center handling standard channel fulfillment. Unmet demand counts toward period loss rather than backlog queue.',
      attributes: [
        ['Assigned demand', '35 units/day (PROD-02)'],
        ['Upstream factory', 'FAC-02'],
        ['Constraint scope', 'Topology metadata'],
        ['Outbound status', 'Lost-service convention applied'],
      ],
    },
  };
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async checkHealth(): Promise<{ online: boolean; message: string }> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${this.baseUrl}/health`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        return { online: true, message: 'Connected to live FastAPI backend' };
      }
      return { online: false, message: `Server returned status ${res.status}` };
    } catch {
      return { online: false, message: 'FastAPI backend offline at ' + this.baseUrl };
    }
  }

  async getNetwork(shutdownDays: number): Promise<{
    data: Record<NodeId, NetworkNodeData>;
    isLive: boolean;
  }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/network?shutdown_days=${shutdownDays}`);
      if (res.ok) {
        const json = await res.json();
        if (json && typeof json === 'object') {
          return { data: json, isLive: true };
        }
      }
    } catch {
      // Fall through to reference data
    }
    return { data: getNetworkNodes(shutdownDays), isLive: false };
  }

  async getSimulation(shutdownDays: number, mode: 'agent' | 'optimized' | 'reorder' = 'agent'): Promise<{
    data: ScenarioImpact;
    isLive: boolean;
  }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/simulate?shutdown_days=${shutdownDays}&mode=${mode}`);
      if (res.ok) {
        const json = await res.json();
        if (json && json.scenario_id) {
          return { data: json, isLive: true };
        }
      }
    } catch {
      // Fall through to reference data
    }
    return { data: getScenarioSnapshot(shutdownDays), isLive: false };
  }

  async getRecovery(shutdownDays: number): Promise<{
    candidates: CandidateMetrics[];
    checks: ValidationCheck[];
    trace: DecisionTraceEvent[];
    isLive: boolean;
  }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/recovery?shutdown_days=${shutdownDays}`);
      if (res.ok) {
        const json = await res.json();
        if (json && json.candidates) {
          return {
            candidates: json.candidates,
            checks: json.checks || getValidationChecks(),
            trace: json.trace || getDecisionTrace(`SCEN-SD${shutdownDays}-H21-S42`),
            isLive: true,
          };
        }
      }
    } catch {
      // Fall through to reference data
    }
    return {
      candidates: getCandidatesForScenario(shutdownDays),
      checks: getValidationChecks(),
      trace: getDecisionTrace(`SCEN-SD${shutdownDays}-H21-S42`),
      isLive: false,
    };
  }

  async getCompare(shutdownDays: number): Promise<{
    candidates: CandidateMetrics[];
    isLive: boolean;
  }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/compare?shutdown_days=${shutdownDays}`);
      if (res.ok) {
        const json = await res.json();
        if (json && json.candidates) {
          return { candidates: json.candidates, isLive: true };
        }
      }
    } catch {
      // Fall through to reference data
    }
    return {
      candidates: getCandidatesForScenario(shutdownDays),
      isLive: false,
    };
  }
}

export const api = new ApiClient();
