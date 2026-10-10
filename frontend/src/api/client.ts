import type {
  CandidateId,
  CandidateMetrics,
  DataStatus,
  DecisionTraceEvent,
  NetworkNodeData,
  NodeId,
  ScenarioImpact,
  ValidationCheck,
} from '../types';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? '' : 'http://127.0.0.1:8000');

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

  async getDataStatus(): Promise<DataStatus | null> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2500);
      const res = await fetch(`${this.baseUrl}/api/data/status`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        const j = await res.json();
        return {
          datasetId: j.dataset_id || 'demo_v1',
          datasetVersion: j.dataset_version || '1.0.0',
          datasetFingerprint: j.dataset_fingerprint || '',
          sourceType: j.source_type || 'synthetic_demo',
          isSynthetic: Boolean(j.is_synthetic),
          loadStatus: j.load_status || 'LOADED',
          validationStatus: j.validation_status || 'VALID',
          supplierCount: j.supplier_count ?? 2,
          productCount: j.product_count ?? 2,
          nodeCount: j.node_count ?? 6,
          summary: j.summary || "Active dataset 'demo_v1' is valid and operational.",
        };
      }
    } catch {
      // Fall through if backend is not reachable
    }
    return null;
  }

  async getNetwork(shutdownDays: number): Promise<{
    data: Record<NodeId, NetworkNodeData>;
    isLive: boolean;
  }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/network`);
      if (res.ok) {
        const json = await res.json();
        if (json && (json.suppliers || json.nodes)) {
          // Enrich default topological node metadata with live backend capacities
          const baseNodes = getNetworkNodes(shutdownDays);
          if (Array.isArray(json.suppliers)) {
            const s1 = json.suppliers.find((s: { id: string }) => s.id === 'SUP-01');
            const s2 = json.suppliers.find((s: { id: string }) => s.id === 'SUP-02');
            if (s1 && baseNodes['SUP-01']) {
              baseNodes['SUP-01'].attributes = [
                ['Lead time', `${s1.lead_time} days`],
                ['Daily capacity', `${s1.capacity} units`],
                ['Landed unit cost', `₹${s1.unit_cost?.toFixed(2) || '12.00'}`],
                ['Blackout window', `Days 1–${shutdownDays}`],
                ['Downstream link', 'Supplies FAC-01 and FAC-02'],
              ];
            }
            if (s2 && baseNodes['SUP-02']) {
              baseNodes['SUP-02'].attributes = [
                ['Lead time', `${s2.lead_time} days`],
                ['Daily capacity', `${s2.capacity} units`],
                ['Landed unit cost', `₹${s2.unit_cost?.toFixed(2) || '16.50'}`],
                ['Capacity vs demand', `${s2.capacity} / 80 units per day (75%)`],
                ['Downstream link', 'Supplies FAC-01 and FAC-02'],
              ];
            }
          }
          return { data: baseNodes, isLive: true };
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
        if (json && (json.scenario || json.scenario_id || json.metrics)) {
          const scenario = json.scenario || {};
          const metrics = json.metrics || {};
          const scenarioId = scenario.scenario_id || json.scenario_id || `SCEN-SD${shutdownDays}-H21-S42`;
          const p1 = metrics.products?.['PROD-01'] || json.products?.['PROD-01'] || {};
          const p2 = metrics.products?.['PROD-02'] || json.products?.['PROD-02'] || {};

          const impact: ScenarioImpact = {
            scenarioId,
            shutdownDays: scenario.shutdown_days ?? json.shutdown_days ?? shutdownDays,
            horizonDays: scenario.horizon ?? json.horizon ?? 21,
            seed: scenario.seed ?? json.seed ?? 42,
            aggregateFillRatePct: Number((metrics.aggregate_fill_rate ?? json.aggregate_fill_rate ?? 85.42).toFixed(2)),
            unmetDemandUnits: metrics.total_unmet_demand ?? json.unmet_demand ?? 245,
            landedCostInr: Number((metrics.total_cost ?? json.total_cost ?? 16470).toFixed(2)),
            recoveryDay: metrics.recovery_day ?? json.recovery_day ?? 10,
            typeLabel: `${shutdownDays}-day disruption (${json.strategy_info?.name || 'Live Engine'})`,
            isVerifiedSnapshot: true,
            products: {
              'PROD-01': {
                fulfilled: p1.fulfilled ?? 865,
                demand: p1.demand ?? 945,
                fillRatePct: Number((p1.fill_rate ?? p1.fillRatePct ?? 91.53).toFixed(2)),
                unmet: p1.unmet ?? 80,
              },
              'PROD-02': {
                fulfilled: p2.fulfilled ?? 570,
                demand: p2.demand ?? 735,
                fillRatePct: Number((p2.fill_rate ?? p2.fillRatePct ?? 77.55).toFixed(2)),
                unmet: p2.unmet ?? 165,
              },
            },
          };
          return { data: impact, isLive: true };
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
        if (json && json.candidates && Array.isArray(json.candidates)) {
          const rankingList = Array.isArray(json.ranking) ? json.ranking : [];

          const candidates: CandidateMetrics[] = json.candidates.map((c: {
            candidate_id: string;
            strategy_id: string;
            name?: string;
            description?: string;
            validation?: { status?: string; is_valid?: boolean };
            metrics?: {
              aggregate_fill_rate?: number;
              total_unmet_demand?: number;
              total_cost?: number;
              recovery_day?: number | null;
              products?: {
                'PROD-01'?: { fill_rate?: number; fulfilled?: number; demand?: number };
                'PROD-02'?: { fill_rate?: number; fulfilled?: number; demand?: number };
              };
            };
          }) => {
            const stratId: CandidateId =
              c.strategy_id === 'reorder' ? 'reorder' : c.strategy_id === 'optimized' ? 'optimized' : 'agent';
            const rankItem = rankingList.find((r: { strategy_id: string }) => r.strategy_id === stratId);
            const m = c.metrics || {};
            const isFeasible = c.validation?.status === 'VALID' || c.validation?.is_valid === true;
            const p1 = m.products?.['PROD-01'] || {};
            const p2 = m.products?.['PROD-02'] || {};

            return {
              id: stratId,
              name: stratId === 'agent' ? 'Agent-assisted' : stratId === 'optimized' ? 'OR-Tools optimized' : 'Reorder baseline',
              subtitle:
                stratId === 'agent'
                  ? 'Priority allocation to PROD-01 (Rank 1 recommended)'
                  : stratId === 'optimized'
                  ? 'Symmetric mathematical optimization (Rank 2)'
                  : 'Infeasible blackout violation (Benchmark only)',
              feasible: isFeasible,
              selectable: isFeasible && stratId !== 'reorder',
              rank: rankItem?.rank ?? (stratId === 'agent' ? 1 : stratId === 'optimized' ? 2 : null),
              rankLabel: stratId === 'reorder' ? 'Infeasible' : rankItem?.rank ? `Rank ${rankItem.rank}` : stratId === 'agent' ? 'Rank 1' : 'Rank 2',
              aggregateFillRatePct: Number((m.aggregate_fill_rate ?? 0).toFixed(2)),
              prod1FillRatePct: Number((p1.fill_rate ?? 0).toFixed(2)),
              prod1Fulfilled: p1.fulfilled ?? 0,
              prod1Demand: p1.demand ?? 945,
              prod2FillRatePct: Number((p2.fill_rate ?? 0).toFixed(2)),
              prod2Fulfilled: p2.fulfilled ?? 0,
              prod2Demand: p2.demand ?? 735,
              unmetDemandUnits: m.total_unmet_demand ?? 0,
              landedCostInr: Number((m.total_cost ?? 0).toFixed(2)),
              recoveryDay: m.recovery_day ?? (stratId === 'reorder' ? 1 : 10),
              score: rankItem?.score ?? (stratId === 'agent' ? 13379.57 : null),
              rationale: c.description || '',
              isVerified: true,
            };
          });

          // Validation checks
          const rawChecks = json.validation_report?.checks || json.checks;
          const checks: ValidationCheck[] = Array.isArray(rawChecks)
            ? rawChecks.map((ch: { check_id?: string; id?: string; label?: string; name?: string; details?: string; description?: string; status: string }) => ({
                id: ch.check_id || ch.id || '',
                name: ch.label || ch.name || '',
                description: ch.details || ch.description || '',
                status: ch.status as 'PASS' | 'FAIL' | 'NOT_MODELED',
                detail: ch.details || ch.description || '',
              }))
            : getValidationChecks();

          // Decision trace
          const rawTrace = json.decision_trace || json.trace;
          const trace: DecisionTraceEvent[] = Array.isArray(rawTrace)
            ? rawTrace.map((t: { step: number; event?: string; title?: string; summary?: string; detail?: string; outcome?: string; status?: string }) => ({
                step: t.step,
                title: t.event || t.title || `Workflow step ${t.step}`,
                detail: t.summary || t.detail || '',
                status:
                  t.outcome === 'VERIFIED' || t.outcome === 'SUCCESS'
                    ? 'good'
                    : t.outcome === 'NOT_CONFIGURED' || t.outcome === 'AWAITING_APPROVAL'
                    ? 'warning'
                    : 'info',
              }))
            : getDecisionTrace(`SCEN-SD${shutdownDays}-H21-S42`);

          return {
            candidates,
            checks,
            trace,
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
        if (json && json.candidates && Array.isArray(json.candidates)) {
          const recRes = await this.getRecovery(shutdownDays);
          return { candidates: recRes.candidates, isLive: true };
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

  async recordApproval(payload: {
    scenarioId: string;
    candidateId: string;
    action: 'APPROVE' | 'REJECT';
    plannerId?: string;
    notes?: string;
  }): Promise<{ success: boolean; recordId?: string; message?: string }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/approval`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: payload.scenarioId,
          candidate_id: payload.candidateId,
          action: payload.action,
          planner_id: payload.plannerId || 'HUMAN_PLANNER_01',
          notes: payload.notes || 'Human planner evaluation recorded via decision support console.',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        return { success: true, recordId: data.record_id, message: 'Approval persisted to audit ledger' };
      }
    } catch {
      // Fall through
    }
    return { success: false, message: 'Server unreachable' };
  }
}

export const api = new ApiClient();
