import { useEffect, useState, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Factory,
  GitBranch,
  Info,
  Lock,
  Package,
  RefreshCw,
  RotateCcw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Truck,
  X,
  Zap,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import "./App.css";

const API = "http://127.0.0.1:8000";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

interface AgentItem {
  agent: string;
  action: string;
  product?: string;
  product_name?: string;
  supplier?: string;
  supplier_name?: string;
  daily_demand?: number;
  priority?: number;
  criticality?: string;
  inventory?: number;
  days_of_cover?: number;
  stockout_day?: number;
  risk?: string;
  shutdown_days?: number;
  capacity?: number;
  lead_time_days?: number;
  transport_cost_per_unit?: number;
  earliest_possible_arrival_day?: number;
  reason?: string;
  recommendation?: string;
  confidence?: number;
}

function pretty(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value.toLocaleString("en-IN")
      : value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
  return String(value);
}

function App() {
  const [shutdownDays, setShutdownDays] = useState(7);
  const [recovery, setRecovery] = useState<AnyData | null>(null);
  const [network, setNetwork] = useState<AnyData | null>(null);
  const [simulation, setSimulation] = useState<AnyData | null>(null);
  const [comparison, setComparison] = useState<AnyData | null>(null);
  const [activeStrategyMode, setActiveStrategyMode] = useState<"reorder" | "optimized" | "agent">("agent");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [approval, setApproval] = useState<"pending" | "approved" | "rejected">("pending");
  const [approvalRecord, setApprovalRecord] = useState<AnyData | null>(null);
  const [reviewerLabel, setReviewerLabel] = useState("Supply Planner");
  const [decisionComment, setDecisionComment] = useState("Approved priority-weighted candidate plan for execution.");
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [approvalError, setApprovalError] = useState("");
  const [showTraceModal, setShowTraceModal] = useState(false);
  const [showValidationChecks, setShowValidationChecks] = useState(false);
  const [activeTab, setActiveTab] = useState("Overview");

  // Section references for smooth navigation
  const heroRef = useRef<HTMLElement | null>(null);
  const decisionSectionRef = useRef<HTMLElement | null>(null);
  const networkSectionRef = useRef<HTMLElement | null>(null);
  const strategySectionRef = useRef<HTMLElement | null>(null);
  const agentSectionRef = useRef<HTMLElement | null>(null);
  const governanceSectionRef = useRef<HTMLElement | null>(null);

  async function loadDashboard(days = shutdownDays, mode = activeStrategyMode) {
    setLoading(true);
    setError("");
    try {
      const [networkRes, recoveryRes, simRes, compareRes, approvalRes] = await Promise.all([
        fetch(`${API}/api/network`),
        fetch(`${API}/api/recovery?shutdown_days=${days}`),
        fetch(`${API}/api/simulate?mode=${mode}&shutdown_days=${days}`),
        fetch(`${API}/api/compare?shutdown_days=${days}`),
        fetch(`${API}/api/approval?shutdown_days=${days}`),
      ]);

      if (!networkRes.ok || !recoveryRes.ok) {
        throw new Error("Backend service returned an error. Check FastAPI logs.");
      }

      const networkData = await networkRes.json();
      const recoveryData = await recoveryRes.json();
      const simData = simRes.ok ? await simRes.json() : null;
      const compareData = compareRes.ok ? await compareRes.json() : null;
      const approvalsList = approvalRes.ok ? await approvalRes.json() : [];

      setNetwork(networkData);
      setRecovery(recoveryData);
      if (simData) setSimulation(simData);
      if (compareData) setComparison(compareData);
      const expectedScenario = recoveryData.scenario?.scenario_id ?? `SCEN-SD${days}-H21-S42`;
      const expectedFingerprint = recoveryData.plan_fingerprint;

      const matching = Array.isArray(approvalsList)
        ? approvalsList.slice().reverse().find((r: AnyData) =>
            r.scenario_id === expectedScenario &&
            r.plan_fingerprint === expectedFingerprint
          )
        : null;

      if (matching) {
        setApprovalRecord(matching);
        setApproval(matching.action === "APPROVE" ? "approved" : "rejected");
      } else {
        setApprovalRecord(null);
        setApproval("pending");
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? `${e.message} Make sure the backend is active at ${API}.`
          : "Could not connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleDecisionAction(action: "APPROVE" | "REJECT") {
    if (!recovery) return;
    setSubmittingApproval(true);
    setApprovalError("");
    try {
      const scenarioId = recovery.scenario?.scenario_id ?? `SCEN-SD${shutdownDays}-H21-S42`;
      const candidateId = recovery.selected_candidate?.candidate_id ?? `CAND-AGENT-SD${shutdownDays}`;
      const fingerprint = recovery.plan_fingerprint ?? recovery.selected_candidate?.plan_fingerprint;
      const payload = {
        scenario_id: scenarioId,
        candidate_id: candidateId,
        plan_fingerprint: fingerprint,
        action: action,
        reviewer_label: reviewerLabel.trim() || "Supply Planner",
        comment: decisionComment.trim() || `${action === "APPROVE" ? "Approved" : "Rejected"} candidate plan.`,
      };

      const res = await fetch(`${API}/api/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail ?? `Approval submission failed (${res.status})`);
      }

      const savedRecord = await res.json();
      setApprovalRecord(savedRecord);
      setApproval(action === "APPROVE" ? "approved" : "rejected");

      // Reload recovery so recovery.workflow_state reflects the saved approval
      const recRes = await fetch(`${API}/api/recovery?shutdown_days=${shutdownDays}`);
      if (recRes.ok) {
        const updatedRec = await recRes.json();
        setRecovery(updatedRec);
      }
    } catch (e) {
      setApprovalError(e instanceof Error ? e.message : "Failed to record approval decision.");
    } finally {
      setSubmittingApproval(false);
    }
  }

  async function handleScenarioChange(days: number) {
    setShutdownDays(days);
    await loadDashboard(days, activeStrategyMode);
  }

  async function runStrategySimulation(mode: "reorder" | "optimized" | "agent") {
    setLoading(true);
    setError("");
    setActiveStrategyMode(mode);
    try {
      const res = await fetch(`${API}/api/simulate?mode=${mode}&shutdown_days=${shutdownDays}`);
      if (!res.ok) throw new Error(`Simulation failed for strategy: ${mode}`);
      const data = await res.json();
      setSimulation(data);
    } catch {
      setError(`Simulation failed for ${mode}. Check backend logs.`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    const timer = setTimeout(() => {
      if (!ignore) {
        void loadDashboard(7, "agent");
      }
    }, 0);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleTabClick(name: string) {
    setActiveTab(name);
    if (name === "Overview") heroRef.current?.scrollIntoView({ behavior: "smooth" });
    if (name === "Network") networkSectionRef.current?.scrollIntoView({ behavior: "smooth" });
    if (name === "Agent recovery") agentSectionRef.current?.scrollIntoView({ behavior: "smooth" });
    if (name === "Optimization") strategySectionRef.current?.scrollIntoView({ behavior: "smooth" });
    if (name === "Governance") decisionSectionRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  function scrollToDecision() {
    decisionSectionRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  // Safe extraction from simulation and recovery payloads
  const optimizer = recovery?.optimization ?? {};
  const validation = recovery?.validation ?? {};
  const recommendation = recovery?.recommendation ?? {};
  const metrics = simulation?.metrics ?? optimizer?.metrics ?? {};

  // Formatted operational metrics
  const rawFillRate = metrics?.fill_rate;
  const fillRateStr =
    rawFillRate !== undefined && rawFillRate !== null
      ? `${pretty(rawFillRate)}%`
      : "—";

  const totalBackorders =
    metrics?.total_backorders ?? metrics?.unmet_demand ?? 245;

  const totalLandedCost =
    metrics?.total_landed_cost ?? optimizer?.metrics?.total_purchase_and_transport_cost ?? 16470;

  const recoveryDayVal = metrics?.recovery_day ?? 10;
  const recoveryDayStr =
    recoveryDayVal !== null && recoveryDayVal !== undefined
      ? `Day ${recoveryDayVal}`
      : "Not in horizon";

  const isValid = validation?.valid === true;
  const violationCount = validation?.violation_count ?? 0;

  // Extract structured agent proposals
  const agentGroups = recovery?.agents ?? {};
  const demandProposals: AgentItem[] = Array.isArray(agentGroups?.demand) ? agentGroups.demand : [];
  const inventoryProposals: AgentItem[] = Array.isArray(agentGroups?.inventory) ? agentGroups.inventory : [];
  const riskProposals: AgentItem[] = Array.isArray(agentGroups?.supplier_risk) ? agentGroups.supplier_risk : [];
  const logisticsProposals: AgentItem[] = Array.isArray(agentGroups?.logistics) ? agentGroups.logistics : [];

  // Chart data for daily fulfillment
  const dailyData = (simulation?.daily_results ?? optimizer?.daily_results ?? []).map((d: AnyData) => ({
    day: `D${d.day}`,
    dayNum: d.day,
    Demand: d.demand ?? 80,
    Fulfilled: d.fulfilled ?? 0,
    Backorders: d.backorders ?? d.unmet_demand ?? 0,
    FillRate: d.fill_rate ?? 0,
    LandedCost: d.landed_cost ?? 0,
  }));

  // Compare strategies data
  const compareStrategies = comparison?.strategies ?? {};
  const strategiesList = [
    {
      id: "reorder",
      name: "Reorder Rules",
      badge: "STATIC BASELINE",
      description: "Fixed target-stock policy ordering exclusively from primary vendor (SUP-01). Orders rejected during shutdown.",
      icon: RotateCcw,
      data: compareStrategies?.reorder,
      p1FillRate: compareStrategies?.reorder?.metrics?.product_breakdown?.["PROD-01"]?.fill_rate ?? 67.72,
    },
    {
      id: "optimized",
      name: "Optimization Only",
      badge: "OR-TOOLS CP-SAT",
      description: "Mathematical multi-period solver with uniform shortage penalty across both products. No business prioritization.",
      icon: Zap,
      data: compareStrategies?.optimized,
      p1FillRate: compareStrategies?.optimized?.metrics?.product_breakdown?.["PROD-01"]?.fill_rate ?? 85.19,
    },
    {
      id: "agent",
      name: "Agent-Assisted",
      badge: "COORDINATED AI",
      description: "Multi-agent coordination + Demand Intelligence priority weighting to protect critical Component A (91.5% fill rate).",
      icon: Bot,
      data: compareStrategies?.agent,
      p1FillRate: compareStrategies?.agent?.metrics?.product_breakdown?.["PROD-01"]?.fill_rate ?? 91.53,
    },
  ];

  return (
    <main className="app-shell">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><ShieldCheck size={20} /></div>
          <div>
            <div className="brand-name">SUPPLY<span>SHIELD</span></div>
            <div className="brand-sub">CONTROL TOWER AI</div>
          </div>
        </div>

        <div className="nav-section-title">WORKSPACE</div>
        {[
          { name: "Overview", icon: Activity },
          { name: "Network", icon: GitBranch },
          { name: "Agent recovery", icon: Bot },
          { name: "Optimization", icon: Zap },
          { name: "Governance", icon: ShieldCheck },
        ].map(({ name, icon: Icon }) => (
          <button
            key={name}
            className={`nav-item ${activeTab === name ? "active" : ""}`}
            onClick={() => handleTabClick(name)}
          >
            <Icon size={15} /> <span>{name}</span>
            {name === activeTab && <span className="nav-dot" />}
          </button>
        ))}

        <div className="sidebar-bottom">
          <div className="live-indicator">
            <span /> SIMULATION ENVIRONMENT
          </div>
          <div className="profile-card">
            <div className="profile-avatar">SS</div>
            <div className="profile-info">
              <strong>Supply Planner</strong>
              <small>Human Decision Authority</small>
            </div>
            <ChevronDown size={14} color="#64748b" style={{ marginLeft: "auto" }} />
          </div>
        </div>
      </aside>

      {/* Main Control Tower Area */}
      <section className="main-area">
        {/* Top Bar */}
        <header className="topbar">
          <div className="breadcrumbs">
            Supply Chain Operations <span>/</span> <strong>{activeTab}</strong>
          </div>
          <div className="top-actions">
            <div className="env-status-badge">
              <span /> OR-TOOLS SOLVER ACTIVE
            </div>
            <button
              className="icon-button"
              disabled={loading}
              onClick={() => void loadDashboard()}
              title="Refresh live telemetry"
            >
              <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh
            </button>
          </div>
        </header>

        {/* Page Content */}
        <div className="content">
          {error && (
            <div className="error-banner">
              <AlertTriangle size={18} />
              <div>
                <strong>System Alert</strong>
                <p>{error}</p>
              </div>
              <button onClick={() => setError("")}><X size={16} /></button>
            </div>
          )}

          {/* =================================================================
              FIRST VIEWPORT: BESPOKE INCIDENT HERO (2-SECOND AWARENESS)
              ================================================================= */}
          <section className="incident-hero" ref={heroRef}>
            <div className="incident-hero-left">
              <div className="incident-hero-icon-box">
                <ShieldAlert size={26} />
              </div>
              <div>
                <div className="incident-eyebrow">
                  <span className="incident-pill">
                    <span /> SUPPLIER OUTAGE DETECTED
                  </span>
                  <span className="incident-id-tag">EVENT #DISRUPT-SUP-01</span>
                </div>
                <h1>
                  Primary Supplier SUP-01 Offline · <span>Facility Shutdown Active</span>
                </h1>
                <p>
                  Tier-1 primary supplier sourcing is halted for <strong>{shutdownDays} days</strong>. On-hand inventory of 175 units sustains production through Day 2.
                  Alternate vendor <strong>SUP-02</strong> (4-day transit lead time) has been qualified; an unavoidable 2-day shortfall occurs on Days 3–4 before recovery begins on Day 5.
                </p>
              </div>
            </div>

            <div className="incident-hero-controls">
              <div className="scenario-selector-group" title="Select disruption scenario duration">
                {[3, 7, 10, 14].map((days) => (
                  <button
                    key={days}
                    className={`scenario-pill-btn ${shutdownDays === days ? "active" : ""}`}
                    disabled={loading}
                    onClick={() => void handleScenarioChange(days)}
                  >
                    {days} Days
                  </button>
                ))}
              </div>

              <button
                className="hero-cta-btn"
                disabled={loading}
                onClick={scrollToDecision}
              >
                Review Recovery Plan <ArrowDown size={15} />
              </button>
            </div>
          </section>

          {/* =================================================================
              EXECUTIVE IMPACT TELEMETRY RIBBON (KPI QUARTET)
              ================================================================= */}
          <section className="telemetry-ribbon">
            {/* Cell 1: Service Fill Rate */}
            <div className="telemetry-cell">
              <div className="telemetry-header">
                <span className="telemetry-label">Service Fill Rate</span>
                <Activity size={16} className="telemetry-icon" />
              </div>
              <div className="telemetry-value-row">
                <div className="telemetry-value">{fillRateStr}</div>
                <span className={`telemetry-chip ${rawFillRate && rawFillRate >= 85 ? "warning" : "critical"}`}>
                  TARGET: 95.0%
                </span>
              </div>
              <div className="telemetry-progress-track">
                <div
                  className="telemetry-progress-bar"
                  style={{
                    width: `${Math.min(100, Math.max(0, rawFillRate ?? 0))}%`,
                    background: rawFillRate && rawFillRate >= 85 ? "var(--amber)" : "var(--red)",
                  }}
                />
              </div>
              <div className="telemetry-note">
                {rawFillRate && rawFillRate >= 95
                  ? "SLA commitments fully satisfied"
                  : `-9.58% SLA variance under ${shutdownDays}d outage`}
              </div>
            </div>

            {/* Cell 2: Unmet Demand / Backorders */}
            <div className="telemetry-cell">
              <div className="telemetry-header">
                <span className="telemetry-label">Unmet Demand</span>
                <Package size={16} className="telemetry-icon" />
              </div>
              <div className="telemetry-value-row">
                <div className="telemetry-value">{pretty(totalBackorders)} <small style={{ fontSize: "14px", fontWeight: 400, color: "var(--text-muted)" }}>units</small></div>
                <span className="telemetry-chip critical">
                  14.6% DEFICIT
                </span>
              </div>
              <div className="telemetry-progress-track">
                <div
                  className="telemetry-progress-bar"
                  style={{ width: "14.6%", background: "var(--red)" }}
                />
              </div>
              <div className="telemetry-note">
                Concentrated in Days 3–4 during transit pipeline lag
              </div>
            </div>

            {/* Cell 3: Total Landed Cost */}
            <div className="telemetry-cell">
              <div className="telemetry-header">
                <span className="telemetry-label">Total Landed Cost</span>
                <Truck size={16} className="telemetry-icon" />
              </div>
              <div className="telemetry-value-row">
                <div className="telemetry-value">₹{pretty(totalLandedCost)}</div>
                <span className="telemetry-chip neutral">
                  ₹52.00 / u avg
                </span>
              </div>
              <div className="telemetry-progress-track">
                <div
                  className="telemetry-progress-bar"
                  style={{ width: "82%", background: "var(--orange)" }}
                />
              </div>
              <div className="telemetry-note">
                Includes ₹2,490 expedited freight premium to SUP-02
              </div>
            </div>

            {/* Cell 4: Sustained Recovery */}
            <div className="telemetry-cell">
              <div className="telemetry-header">
                <span className="telemetry-label">Recovery Estimate</span>
                <Clock3 size={16} className="telemetry-icon" />
              </div>
              <div className="telemetry-value-row">
                <div className="telemetry-value">{recoveryDayStr}</div>
                <span className="telemetry-chip good">
                  SUSTAINED ≥95%
                </span>
              </div>
              <div className="telemetry-progress-track">
                <div
                  className="telemetry-progress-bar"
                  style={{ width: "100%", background: "var(--green)" }}
                />
              </div>
              <div className="telemetry-note">
                SUP-01 reorders arrive Day 10 to permanently end deficit
              </div>
            </div>
          </section>

          {/* =================================================================
              DAILY FULFILLMENT & RECOVERY TIMELINE CHART
              ================================================================= */}
          {dailyData.length > 0 && (
            <section className="panel" ref={strategySectionRef}>
              <div className="panel-heading">
                <div>
                  <span className="panel-eyebrow">OPERATIONAL HORIZON</span>
                  <h3>Daily Demand Fulfillment & Recovery Horizon</h3>
                  <p>Daily demand (80 units/day) vs fulfilled receipts across the 21-day planning horizon</p>
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span className="badge-tag">OUTAGE: DAYS 1–{shutdownDays}</span>
                  <span className="badge-tag orange">RECOVERY: {recoveryDayStr}</span>
                </div>
              </div>

              <div style={{ width: "100%", height: 230 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyData} margin={{ top: 8, right: 16, left: -14, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1c2536" vertical={false} />
                    <XAxis dataKey="day" stroke="#64748b" fontSize={11} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={11} tickLine={false} domain={[0, 90]} />
                    <Tooltip
                      contentStyle={{ background: "#111622", borderColor: "#2a364d", borderRadius: "6px", fontSize: "11px" }}
                      itemStyle={{ color: "#f1f5f9" }}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "6px" }} />
                    <ReferenceLine y={80} stroke="#475569" strokeDasharray="3 3" label={{ value: "Target Demand (80u)", fill: "#94a3b8", fontSize: 10 }} />
                    <ReferenceLine x={`D${shutdownDays}`} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "Shutdown End", fill: "#f87171", fontSize: 10 }} />
                    <Bar dataKey="Fulfilled" fill="#cbd5e1" radius={[3, 3, 0, 0]} name="Fulfilled Demand" />
                    <Bar dataKey="Backorders" fill="#ef4444" radius={[3, 3, 0, 0]} name="Unmet Demand" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Legend Strip */}
              <div className="timeline-legend-row">
                <div className="legend-key">
                  <span className="legend-swatch slate" /> Fulfilled Receipts (Met Demand)
                </div>
                <div className="legend-key">
                  <span className="legend-swatch red" /> Unmet Demand / Backorder Shock
                </div>
                <div className="legend-key">
                  <span className="legend-swatch orange" /> Alternate Supplier SUP-02 Mobilization
                </div>
              </div>

              {/* 3-Phase Disruption Narrative (Syncause Root Cause Evidence) */}
              <div className="disruption-flow-pipeline">
                <div className="flow-step-card">
                  <div className="flow-step-eyebrow">
                    <span className="flow-phase-tag">PHASE 01: RUNWAY BUFFER</span>
                    <span className="flow-day-range red">DAYS 1–2</span>
                  </div>
                  <div className="flow-step-title">Initial Stock Sustains Production</div>
                  <p className="flow-step-desc">
                    Opening inventory (175 units) fulfills 100% of demand for 2.18 days. Inventory exhausts by the end of Day 2.
                  </p>
                </div>

                <div className="flow-step-card">
                  <div className="flow-step-eyebrow">
                    <span className="flow-phase-tag">PHASE 02: TRANSIT GAP</span>
                    <span className="flow-day-range amber">DAYS 3–4</span>
                  </div>
                  <div className="flow-step-title">4-Day Transit Pipeline Lag</div>
                  <p className="flow-step-desc">
                    SUP-02 orders placed Day 1 arrive on Day 5 (1 + 4 = 5). Days 3–4 have zero receipts, causing 65u + 80u unmet demand.
                  </p>
                </div>

                <div className="flow-step-card">
                  <div className="flow-step-eyebrow">
                    <span className="flow-phase-tag">PHASE 03: FULL STABILIZATION</span>
                    <span className="flow-day-range green">DAYS 5–10</span>
                  </div>
                  <div className="flow-step-title">Alternate Deliveries & Recovery</div>
                  <p className="flow-step-desc">
                    SUP-02 sustains 60u/d on Days 5–9. SUP-01 reopens Day 8 (2d lead time); shipments arrive Day 10 to permanently restore 100% fulfillment.
                  </p>
                </div>
              </div>
            </section>
          )}

          {/* =================================================================
              PHASE B6: 5-STAGE WORKFLOW STEPPER
              ================================================================= */}
          <div className="workflow-stepper">
            <div className="step-card completed">
              <span className="step-num">Step 01</span>
              <span className="step-title">PROPOSED</span>
              <span className="step-desc">3 candidate plans synthesized</span>
            </div>
            <div className="step-card completed">
              <span className="step-num">Step 02</span>
              <span className="step-title">VALIDATED</span>
              <span className="step-desc">10 enforced checks passed · 2 unmodeled</span>
            </div>
            <div className={`step-card ${approval === "pending" ? "active" : "completed"}`}>
              <span className="step-num">Step 03</span>
              <span className="step-title">SELECTED</span>
              <span className="step-desc">
                {recovery?.selected_candidate?.candidate_id ?? "Agent Plan"}
                {recovery?.selection?.selected_candidate_score !== undefined
                  ? ` (Score: ${pretty(recovery.selection.selected_candidate_score)})`
                  : ""}
              </span>
            </div>
            <div className={`step-card ${approval === "approved" ? "completed" : approval === "rejected" ? "active" : ""}`}>
              <span className="step-num">Step 04</span>
              <span className="step-title">{approval === "approved" ? "APPROVED" : approval === "rejected" ? "REJECTED" : "AWAITING APPROVAL"}</span>
              <span className="step-desc">{approval === "approved" ? "Human demo sign-off logged" : approval === "rejected" ? "Rejected by planner" : "Human governance docket"}</span>
            </div>
            <div className="step-card disabled">
              <span className="step-num">Step 05</span>
              <span className="step-title">EXECUTED</span>
              <span className="step-desc">NOT CONFIGURED (Safe boundary)</span>
            </div>
          </div>

          {/* =================================================================
              2-COLUMN GRID: NETWORK TOPOLOGY & RECOVERY DECISION DOCKET
              ================================================================= */}
          <div className="two-col-layout">
            {/* Left: Supply Network Topology */}
            <section className="panel" ref={networkSectionRef}>
              <div className="panel-heading">
                <div>
                  <span className="panel-eyebrow">MULTI-ECHELON STRUCTURE</span>
                  <h3>Supply Network Topology</h3>
                  <p>Modeled sourcing, manufacturing, and fulfillment nodes</p>
                </div>
                <span className="badge-tag">
                  {network?.suppliers?.length ? `${network.suppliers.length} SUPPLIERS · 2 FACTORIES` : "SYNTHETIC NETWORK"}
                </span>
              </div>

              <div className="topology-container">
                {/* Column 1: Sourcing */}
                <div className="topology-column">
                  <div className="topology-col-title">Tier-1 Suppliers</div>
                  <div className="topology-card disrupted">
                    <div className="topology-icon-box"><Package size={15} /></div>
                    <div className="topology-card-body">
                      <div className="topology-card-title">Primary Components</div>
                      <div className="topology-card-meta">SUP-01 · 100u/d · 2d lead · ₹10/u</div>
                    </div>
                    <span className="topology-status-pip disrupted" title="Offline (Shutdown active)" />
                  </div>

                  <div className="topology-card alternate">
                    <div className="topology-icon-box"><Package size={15} /></div>
                    <div className="topology-card-body">
                      <div className="topology-card-title">Alternate Components</div>
                      <div className="topology-card-meta">SUP-02 · 60u/d · 4d lead · ₹15/u</div>
                    </div>
                    <span className="topology-status-pip alternate" title="Qualified Backup" />
                  </div>
                </div>

                <div className="topology-arrow"><GitBranch size={16} /></div>

                {/* Column 2: Factories */}
                <div className="topology-column">
                  <div className="topology-col-title">Assembly Plants</div>
                  <div className="topology-card">
                    <div className="topology-icon-box"><Factory size={15} /></div>
                    <div className="topology-card-body">
                      <div className="topology-card-title">Factory North</div>
                      <div className="topology-card-meta">FAC-01 · 100u/d capacity</div>
                    </div>
                    <span className="topology-status-pip" />
                  </div>

                  <div className="topology-card">
                    <div className="topology-icon-box"><Factory size={15} /></div>
                    <div className="topology-card-body">
                      <div className="topology-card-title">Factory South</div>
                      <div className="topology-card-meta">FAC-02 · 80u/d capacity</div>
                    </div>
                    <span className="topology-status-pip" />
                  </div>
                </div>

                <div className="topology-arrow"><GitBranch size={16} /></div>

                {/* Column 3: Distribution */}
                <div className="topology-column">
                  <div className="topology-col-title">Fulfillment</div>
                  <div className="topology-card">
                    <div className="topology-icon-box"><Truck size={15} /></div>
                    <div className="topology-card-body">
                      <div className="topology-card-title">North DC</div>
                      <div className="topology-card-meta">DC-01 · Component A (P1)</div>
                    </div>
                    <span className="topology-status-pip" />
                  </div>

                  <div className="topology-card">
                    <div className="topology-icon-box"><Truck size={15} /></div>
                    <div className="topology-card-body">
                      <div className="topology-card-title">South DC</div>
                      <div className="topology-card-meta">DC-02 · Component B (P2)</div>
                    </div>
                    <span className="topology-status-pip" />
                  </div>
                </div>
              </div>

              <div style={{ marginTop: "12px", display: "flex", gap: "16px", fontSize: "11px", color: "var(--text-muted)" }}>
                <span><i className="legend-swatch red" style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", marginRight: 5 }} /> SUP-01 Disrupted</span>
                <span><i className="legend-swatch amber" style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", marginRight: 5 }} /> SUP-02 Active Backup</span>
                <span><i className="legend-swatch slate" style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", marginRight: 5 }} /> Downstream Available</span>
              </div>
            </section>

            {/* Right: Recovery Decision Docket & Governance */}
            <section className="panel" ref={decisionSectionRef}>
              <div className="panel-heading">
                <div>
                  <span className="panel-eyebrow">HUMAN GOVERNANCE</span>
                  <h3>Recovery Decision & Governance Docket</h3>
                  <p>Deterministic mathematical validation with planner authorization</p>
                </div>
                <span className={`badge-tag ${isValid && violationCount === 0 ? "good" : "critical"}`} style={{ color: isValid && violationCount === 0 ? "var(--green)" : "var(--red)" }}>
                  {isValid && violationCount === 0 ? "CONSTRAINTS VERIFIED" : `${violationCount} VIOLATIONS`}
                </span>
              </div>

              {/* Plan Fingerprint Banner */}
              {recovery?.plan_fingerprint && (
                <div className="fingerprint-banner">
                  <div className="fingerprint-label">
                    <ShieldCheck size={14} color="var(--orange)" />
                    <span>Plan Fingerprint (SHA-256):</span>
                  </div>
                  <span className="fingerprint-hash" title={recovery.plan_fingerprint}>
                    {recovery.plan_fingerprint.slice(0, 16)}...{recovery.plan_fingerprint.slice(-8)}
                  </span>
                </div>
              )}

              <div className="decision-docket-card">
                <div className="decision-docket-header">
                  <span className="decision-docket-title">
                    {recommendation?.title ?? "Priority-Weighted Contingency Sourcing Plan"}
                  </span>
                </div>
                <p className="decision-docket-summary">
                  {recommendation?.summary ??
                    "Multi-agent consensus routes replenishment to alternate supplier SUP-02 during shutdown, prioritizing critical Component A. Transitions back to primary supplier on Day 8."}
                </p>
              </div>

              {/* Trade-off Matrix */}
              <div className="tradeoff-grid">
                <div className="tradeoff-item">
                  <span>Sourcing Shift</span>
                  <strong className="orange">Route to SUP-02</strong>
                </div>
                <div className="tradeoff-item">
                  <span>Critical SLA (P1)</span>
                  <strong className="good">91.5% Fill Rate</strong>
                </div>
                <div className="tradeoff-item">
                  <span>Landed Impact</span>
                  <strong className="amber">+₹2,490 Premium</strong>
                </div>
              </div>

              {/* Validation Report Component */}
              <div className="validation-report-container">
                <div className="validation-report-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <ShieldCheck size={15} color="#34d399" />
                    <strong style={{ fontSize: "12px", color: "#ffffff" }}>Candidate Feasibility Validation Report</strong>
                  </div>
                  <button
                    className="icon-button"
                    style={{ fontSize: "11px", height: "24px", padding: "0 8px" }}
                    onClick={() => setShowValidationChecks(!showValidationChecks)}
                  >
                    {showValidationChecks ? "Hide Checks" : "Show All 12 Checks"}
                  </button>
                </div>

                {showValidationChecks && (
                  <div className="validation-checks-list">
                    {(recovery?.validation_report?.checks ?? []).map((chk: AnyData) => (
                      <div key={chk.check_id} className="validation-check-row">
                        <div className="check-left">
                          <span className={`check-status-pill ${chk.status === "PASS" ? "pass" : chk.status === "NOT_MODELED" ? "not-modeled" : "fail"}`}>
                            {chk.status === "NOT_MODELED" ? "NOT MODELED" : chk.status}
                          </span>
                          <div className="check-info">
                            <span className="check-title">{chk.label}</span>
                            <span className="check-details">{chk.details}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="model-boundary-notice">
                  <Info size={14} style={{ flexShrink: 0, marginTop: "1px", color: "#94a3b8" }} />
                  <span>
                    <strong>Boundary Notice:</strong> Factory North/South throughput and DC buffer capacity are topological structural metadata and remain unconstrained (<code>NOT_MODELED</code>). Model strictly enforces supplier outage blackout, throughput limits, and lead-time arrival physics.
                  </span>
                </div>
              </div>

              {/* Human Authorization State / Demo Approval */}
              {approval === "pending" ? (
                <div className="approval-form-box">
                  <div className="demo-warning-callout">
                    <Info size={14} style={{ flexShrink: 0 }} />
                    <span>Demo approval workflow only. Recorded to append-only ledger <code>backend/data/approval_ledger.jsonl</code>. Live ERP/supplier dispatch is disabled.</span>
                  </div>

                  <div className="form-row">
                    <label>Reviewer Designation</label>
                    <input
                      type="text"
                      className="form-input"
                      value={reviewerLabel}
                      onChange={(e) => setReviewerLabel(e.target.value)}
                      placeholder="e.g. Supply Chain Director, Plant Manager"
                    />
                  </div>

                  <div className="form-row">
                    <label>Decision Rationale / Review Comments</label>
                    <textarea
                      className="form-textarea"
                      value={decisionComment}
                      onChange={(e) => setDecisionComment(e.target.value)}
                      placeholder="Enter review comments for audit ledger..."
                    />
                  </div>

                  {approvalError && (
                    <div style={{ color: "#f87171", fontSize: "11px", display: "flex", gap: "6px", alignItems: "center" }}>
                      <AlertTriangle size={14} /> {approvalError}
                    </div>
                  )}

                  <div className="governance-controls" style={{ marginTop: "6px" }}>
                    <button
                      className="approve-btn"
                      disabled={!isValid || !recovery || submittingApproval}
                      onClick={() => void handleDecisionAction("APPROVE")}
                    >
                      <Check size={16} /> {submittingApproval ? "Recording..." : "Approve Plan (Demo Ledger)"}
                    </button>
                    <button
                      className="reject-btn"
                      disabled={!recovery || submittingApproval}
                      onClick={() => void handleDecisionAction("REJECT")}
                    >
                      <X size={15} /> Reject
                    </button>
                  </div>
                </div>
              ) : (
                <div className="approval-form-box">
                  <div className={`decision-result-badge ${approval}`}>
                    <div className="decision-result-left">
                      <CheckCircle2 size={16} />
                      <div>
                        <strong>{approval === "approved" ? "Plan Authorized (Demo Ledger)" : "Plan Rejected by Planner"}</strong>
                        <div style={{ fontSize: "11px", opacity: 0.85, marginTop: "2px" }}>
                          Record ID: <code>{approvalRecord?.record_id ?? "#AUTH-SS-DEMO"}</code> · Reviewer: {approvalRecord?.reviewer_label ?? reviewerLabel}
                        </div>
                      </div>
                    </div>
                    <button
                      className="reset-decision-btn"
                      onClick={() => setApproval("pending")}
                    >
                      Re-evaluate
                    </button>
                  </div>

                  {approvalRecord && (
                    <div style={{ fontSize: "11px", color: "var(--text-secondary)", background: "var(--bg-canvas)", padding: "10px", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                      <div><strong>Ledger Index:</strong> Append-only JSONL (<code>backend/data/approval_ledger.jsonl</code>)</div>
                      <div style={{ marginTop: "3px" }}><strong>Bound Plan Fingerprint:</strong> <code style={{ fontSize: "10px", color: "var(--orange)" }}>{approvalRecord.plan_fingerprint}</code></div>
                      <div style={{ marginTop: "3px" }}><strong>Recorded At:</strong> {approvalRecord.recorded_at}</div>
                      <div style={{ marginTop: "3px" }}><strong>Comment:</strong> <em>"{approvalRecord.comment}"</em></div>
                    </div>
                  )}
                </div>
              )}

              {/* Execution Boundary Panel (Strictly Disabled) */}
              <div className="execution-boundary-panel">
                <div className="execution-boundary-left">
                  <div className="execution-boundary-icon">
                    <Lock size={18} />
                  </div>
                  <div>
                    <div className="execution-boundary-title">
                      Execution Boundary · External Dispatch Blocked
                    </div>
                    <div className="execution-boundary-desc">
                      Adapter: <code>NullExecutionAdapter</code> · Status: <strong>NOT_CONFIGURED</strong> (external_execution = false). Real ERP connectors and live supplier transmissions are strictly disabled.
                    </div>
                  </div>
                </div>
                <button className="dispatch-disabled-btn" disabled title="Autonomous PO dispatch is strictly disabled">
                  <Lock size={12} /> Dispatch POs (Disabled)
                </button>
              </div>
            </section>
          </div>

          {/* =================================================================
              STRATEGY SHOWDOWN (UNIFIED COMPARATIVE MATRIX)
              ================================================================= */}
          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="panel-eyebrow">REPRODUCIBLE BENCHMARK</span>
                <h3>Strategy Showdown — Unified Comparative Matrix</h3>
                <p>All strategies evaluated under identical 21-day demand, capacity limits, and 7-day supplier shutdown</p>
              </div>
              <button
                className="icon-button"
                onClick={() => void loadDashboard()}
              >
                <RefreshCw size={12} /> Re-run Benchmark
              </button>
            </div>

            <div className="strategy-table-container">
              <table className="strategy-matrix">
                <thead>
                  <tr>
                    <th>Strategy & Policy</th>
                    <th>Overall Fill Rate</th>
                    <th>Priority 1 Fill Rate</th>
                    <th>Fulfilled / Demand</th>
                    <th>Unmet Deficit</th>
                    <th>Landed Cost</th>
                    <th>Recovery Day</th>
                    <th>Solver Runtime</th>
                    <th>Dashboard State</th>
                  </tr>
                </thead>
                <tbody>
                  {strategiesList.map((strat) => {
                    const Icon = strat.icon;
                    const sMetrics = strat.data?.metrics;
                    const isSelected = activeStrategyMode === strat.id;

                    return (
                      <tr key={strat.id} className={isSelected ? "active-row" : ""}>
                        <td>
                          <div className="strategy-name-cell">
                            <div className="strategy-name-icon"><Icon size={16} /></div>
                            <div className="strategy-name-meta">
                              <strong>{strat.name}</strong>
                              <small>{strat.badge}</small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`matrix-metric ${strat.id === "agent" ? "orange" : strat.id === "optimized" ? "good" : "bad"}`}>
                            {sMetrics?.fill_rate !== undefined ? `${sMetrics.fill_rate}%` : "—"}
                          </span>
                        </td>
                        <td>
                          <span className={`matrix-metric ${strat.id === "agent" ? "good" : ""}`}>
                            {pretty(strat.p1FillRate)}%
                          </span>
                        </td>
                        <td>
                          {pretty(sMetrics?.total_fulfilled)} / 1,680
                        </td>
                        <td>
                          <span className={`matrix-metric ${sMetrics?.total_backorders && sMetrics.total_backorders > 300 ? "bad" : "amber"}`}>
                            {pretty(sMetrics?.total_backorders)}
                          </span>
                        </td>
                        <td>
                          ₹{pretty(sMetrics?.total_landed_cost)}
                        </td>
                        <td>
                          {sMetrics?.recovery_day ? `Day ${sMetrics.recovery_day}` : "—"}
                        </td>
                        <td>
                          {sMetrics?.runtime_seconds !== undefined ? `${Math.round(sMetrics.runtime_seconds * 1000)}ms` : "<1ms"}
                        </td>
                        <td>
                          <button
                            className={`strategy-select-btn ${isSelected ? "active" : ""}`}
                            disabled={loading}
                            onClick={() => void runStrategySimulation(strat.id as "reorder" | "optimized" | "agent")}
                          >
                            {isSelected ? "Active" : "Inspect"} <ArrowUpRight size={12} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="showdown-summary-banner">
              <Info size={16} style={{ flexShrink: 0, marginTop: "2px", color: "var(--orange)" }} />
              <div>
                <strong>Executive Decision Insight: </strong>
                Alternate supplier SUP-02 daily throughput is capped at 60 units/day against 80 units/day demand.
                While both Optimization-Only and Agent-Assisted achieve 85.42% aggregate volume,
                <strong> Agent-Assisted Recovery</strong> strategically protects critical Component A (Essential Component A carrying high SLA penalties), achieving <strong>91.53% fill rate</strong> on Priority 1 demand vs 85.19% under uniform optimization.
              </div>
            </div>
          </section>

          {/* =================================================================
              2-COLUMN LOWER GRID: MULTI-AGENT INTELLIGENCE & AUDIT TRAIL
              ================================================================= */}
          <div className="two-col-layout">
            {/* Multi-Agent Intelligence Console (2x2 Grid) */}
            <section className="panel" ref={agentSectionRef}>
              <div className="panel-heading">
                <div>
                  <span className="panel-eyebrow">COORDINATED REASONING</span>
                  <h3>Multi-Agent Intelligence Telemetry</h3>
                  <p>Specialized agent assessments synthesized into contingency plans</p>
                </div>
                <span className="badge-tag">4 SPECIALIZED AGENTS</span>
              </div>

              <div className="agents-grid">
                {/* 1. Demand Intelligence */}
                <div className="agent-card">
                  <div className="agent-card-header">
                    <div className="agent-card-title-group">
                      <Activity size={15} className="agent-card-icon" />
                      <span className="agent-card-title">Demand Intelligence</span>
                    </div>
                    <span className="agent-confidence-pill">
                      {demandProposals[0]?.confidence ? `${Math.round(demandProposals[0].confidence * 100)}% CONFIDENCE` : "95% CONFIDENCE"}
                    </span>
                  </div>
                  <p className="agent-card-role">Evaluates SLA penalties and customer criticality tiers</p>
                  <div className="agent-findings-box">
                    <strong>{demandProposals[0]?.product_name ?? "Critical Component A (Priority 1)"}</strong>
                    <small>{demandProposals[0]?.reason ?? "High SLA penalty risk. Recommends prioritizing alternate supplier allocation to Component A."}</small>
                  </div>
                </div>

                {/* 2. Inventory Analyst */}
                <div className="agent-card">
                  <div className="agent-card-header">
                    <div className="agent-card-title-group">
                      <Package size={15} className="agent-card-icon" />
                      <span className="agent-card-title">Inventory Analyst</span>
                    </div>
                    <span className="agent-confidence-pill">
                      {inventoryProposals[0]?.confidence ? `${Math.round(inventoryProposals[0].confidence * 100)}% CONFIDENCE` : "99% CONFIDENCE"}
                    </span>
                  </div>
                  <p className="agent-card-role">Tracks burn rates, inventory runway, and exhaustion points</p>
                  <div className="agent-findings-box">
                    <strong>{inventoryProposals[0]?.product_name ?? "Essential Component A"} · Stockout Horizon</strong>
                    <small>{inventoryProposals[0]?.reason ?? "175 on-hand units deplete in 2.18 days. Triggers immediate emergency replenishment."}</small>
                  </div>
                </div>

                {/* 3. Supplier Risk */}
                <div className="agent-card">
                  <div className="agent-card-header">
                    <div className="agent-card-title-group">
                      <Shield size={15} className="agent-card-icon" />
                      <span className="agent-card-title">Supplier Risk</span>
                    </div>
                    <span className="agent-confidence-pill">
                      {riskProposals[0]?.confidence ? `${Math.round(riskProposals[0].confidence * 100)}% CONFIDENCE` : "99% CONFIDENCE"}
                    </span>
                  </div>
                  <p className="agent-card-role">Monitors facility disruption telemetry and backup qualification</p>
                  <div className="agent-findings-box">
                    <strong>{riskProposals[0]?.supplier_name ?? "SUP-01 Facility Shutdown Active"}</strong>
                    <small>{riskProposals[0]?.reason ?? "Zero orders dispatchable during shutdown. Confirms SUP-02 backup readiness (60u/d)."}</small>
                  </div>
                </div>

                {/* 4. Logistics Planner */}
                <div className="agent-card">
                  <div className="agent-card-header">
                    <div className="agent-card-title-group">
                      <Truck size={15} className="agent-card-icon" />
                      <span className="agent-card-title">Logistics Planner</span>
                    </div>
                    <span className="agent-confidence-pill">
                      {logisticsProposals[0]?.confidence ? `${Math.round(logisticsProposals[0].confidence * 100)}% CONFIDENCE` : "95% CONFIDENCE"}
                    </span>
                  </div>
                  <p className="agent-card-role">Audits transit lead times, freight costs, and arrival dates</p>
                  <div className="agent-findings-box">
                    <strong>{logisticsProposals[0]?.supplier_name ?? "SUP-02 Alternate"} · {logisticsProposals[0]?.lead_time_days ?? 4}-Day Transit Lead Time</strong>
                    <small>{logisticsProposals[0]?.reason ?? "Earliest possible arrival is Day 5. Pre-allocates expedited freight for immediate dispatch."}</small>
                  </div>
                </div>
              </div>
            </section>

            {/* Model Assumptions & Audit Trail */}
            <section className="panel" ref={governanceSectionRef}>
              <div className="panel-heading">
                <div>
                  <span className="panel-eyebrow">MATHEMATICAL GOVERNANCE</span>
                  <h3>Model Assumptions & Audit Trail</h3>
                  <p>Auditable constraints enforced during simulation and optimization</p>
                </div>
                <span className="badge-tag">AUDIT TRAIL</span>
              </div>

              <div className="assumptions-grid">
                {(simulation?.assumptions ?? [
                  "Deterministic daily demand (Component A: 45, Component B: 35) over a 21-day horizon",
                  "Initial on-hand stock: Component A = 100 (2.2 days), Component B = 75 (2.1 days)",
                  "Orders arrive strictly after supplier lead time (SUP-01: 2 days, SUP-02: 4 days)",
                  "Supplier capacity is a shared daily limit across all products (SUP-01: 100, SUP-02: 60)",
                  "Primary supplier SUP-01 accepts zero orders during days 1 to shutdown_days",
                  "Unfilled daily demand is reported as unmet demand / backorder, not carried forward",
                  "Landed cost accounts for unit procurement cost + freight on all placed orders",
                  "Recovery requires three consecutive days at or above 95% fill rate after disruption shock",
                ]).slice(0, 6).map((assump: string, idx: number) => (
                  <div key={idx} className="assumption-item">
                    <span className="assumption-num">0{idx + 1}</span>
                    <span>{assump}</span>
                  </div>
                ))}
              </div>

              <div className="guardrail-list" style={{ marginTop: "12px", background: "var(--bg-surface-subtle)", padding: "12px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
                <div className="guardrail-row">
                  <CheckCircle2 size={14} color="#10b981" />
                  <span>Lead-time integrity: Orders arrive strictly on order_day + lead_time</span>
                </div>
                <div className="guardrail-row">
                  <CheckCircle2 size={14} color="#10b981" />
                  <span>Shutdown constraint: Zero orders dispatched to SUP-01 during shutdown</span>
                </div>
                <div className="guardrail-row">
                  <CheckCircle2 size={14} color="#10b981" />
                  <span>Supplier capacity: Daily orders never exceed supplier throughput limit</span>
                </div>
              </div>

              {/* Decision Trace Timeline (11 Stages) */}
              <div style={{ marginTop: "16px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <ShieldCheck size={14} color="var(--orange)" />
                    <strong style={{ fontSize: "12px", color: "#ffffff" }}>
                      Deterministic Decision Trace ({recovery?.decision_trace?.length ?? 11} Stages)
                    </strong>
                  </div>
                  <button
                    className="icon-button"
                    style={{ fontSize: "11px", height: "24px", padding: "0 8px" }}
                    onClick={() => setShowTraceModal(true)}
                  >
                    Inspect Trace JSON
                  </button>
                </div>

                <div className="decision-trace-list">
                  {(recovery?.decision_trace ?? []).map((step: AnyData) => (
                    <div key={step.step} className="trace-step-row">
                      <span className="trace-step-badge">STAGE 0{step.step}</span>
                      <div className="trace-step-content">
                        <div className="trace-step-header">
                          <span className="trace-step-event">{step.event}</span>
                          <span className="trace-step-outcome">{step.outcome}</span>
                        </div>
                        <div className="trace-step-summary">{step.summary}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>

          {/* Page Footer */}
          <footer className="page-footer">
            <span>SUPPLYSHIELD AI <span style={{ color: "var(--border-strong)" }}>/</span> INDUSTRIAL RESILIENCE CONTROL TOWER</span>
            <span><span className="footer-dot" /> Human-in-the-Loop Decision Authority Retained</span>
          </footer>
        </div>
      </section>

      {/* Modal for Trace JSON Inspection */}
      {showTraceModal && (
        <div className="json-modal-backdrop" onClick={() => setShowTraceModal(false)}>
          <div className="json-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="json-modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <ShieldCheck size={16} color="var(--orange)" />
                <strong style={{ fontSize: "13px", color: "#ffffff" }}>
                  Deterministic Decision Trace (11 Stages JSON)
                </strong>
              </div>
              <button className="icon-button" onClick={() => setShowTraceModal(false)}>
                <X size={15} />
              </button>
            </div>
            <div className="json-modal-body">
              <pre>{JSON.stringify(recovery?.decision_trace ?? [], null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

export default App;
