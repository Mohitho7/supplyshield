import React from 'react';
import { useScenario } from '../context/useScenario';
import type { NodeId } from '../types';

export const SupplyNetwork: React.FC = () => {
  const {
    networkNodes,
    selectedNodeId,
    setSelectedNodeId,
    scenarioId,
    setPage,
  } = useScenario();

  const selectedNode = networkNodes[selectedNodeId] || networkNodes['SUP-01'];

  const nodeColumns: { title: string; nodes: NodeId[] }[] = [
    { title: 'Suppliers', nodes: ['SUP-01', 'SUP-02'] },
    { title: 'Factories', nodes: ['FAC-01', 'FAC-02'] },
    { title: 'Distribution', nodes: ['DC-01', 'DC-02'] },
  ];

  return (
    <section className="page" id="page-network" aria-label="Supply network">
      <div className="page-head">
        <div>
          <div className="eyebrow">Understand propagation</div>
          <h1>Supply network</h1>
          <p className="subtitle">
            Inspect the supplier-to-factory-to-distribution-center topology and understand where the
            disruption enters the network and propagates downstream.
          </p>
        </div>
        <span className="scenario-pill">{scenarioId}</span>
      </div>

      <div className="grid grid-2">
        {/* Topology Node Map */}
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Network topology</h2>
              <p>Select a node to inspect its operational role and modeled constraints.</p>
            </div>
            <span className="status status-warning">Primary supplier offline</span>
          </div>

          <div className="panel-body">
            <div className="node-grid" id="networkNodes">
              {nodeColumns.map((col) => (
                <div key={col.title} className="node-column">
                  <div className="node-column-title">{col.title}</div>
                  {col.nodes.map((nodeId) => {
                    const node = networkNodes[nodeId];
                    if (!node) return null;
                    const isSelected = selectedNodeId === nodeId;

                    return (
                      <button
                        key={nodeId}
                        type="button"
                        className="node"
                        aria-pressed={isSelected}
                        onClick={() => setSelectedNodeId(nodeId)}
                      >
                        <div className="node-header">
                          <span className="node-id">{node.id}</span>
                          <span className={`status ${node.statusClass}`}>{node.status}</span>
                        </div>
                        <strong>{node.name}</strong>
                        <small>{node.role}</small>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="layout-note" style={{ marginTop: '16px' }}>
              <strong>Multi-echelon flow context:</strong> Suppliers feed Factories directly; Factories feed
              dedicated Distribution Centers. Factory capacity and DC transfer latency are modeled as
              structural metadata and are not actively constrained in this decision layer.
            </div>
          </div>
        </section>

        {/* Selected Node Inspector */}
        <section className="panel node-inspector" id="nodeInspector" aria-live="polite">
          <div className="panel-head">
            <div>
              <h2>{selectedNode.id} · {selectedNode.name}</h2>
              <p>Selected node configuration</p>
            </div>
            <span className={`status ${selectedNode.statusClass}`}>{selectedNode.status}</span>
          </div>

          <div className="panel-body">
            <p className="body-copy">{selectedNode.description}</p>

            <dl className="detail-list" style={{ marginTop: '16px' }}>
              {selectedNode.attributes.map(([key, val]) => (
                <React.Fragment key={key}>
                  <dt>{key}</dt>
                  <dd>{val}</dd>
                </React.Fragment>
              ))}
              <dt>Active Scenario</dt>
              <dd>{scenarioId}</dd>
            </dl>

            <div className="layout-note" style={{ marginTop: '17px' }}>
              <strong>Model boundary note:</strong> Constraints on {selectedNode.id} follow explicit simulator
              rules. No unverified supplier telematics, live inventory APIs, or ERP stockout alerts are
              fabricated.
            </div>

            <button
              className="btn btn-primary"
              type="button"
              style={{ marginTop: '16px', width: '100%' }}
              onClick={() => setPage('recovery')}
            >
              Review recovery response →
            </button>
          </div>
        </section>
      </div>

      {/* Reading Guide */}
      <section className="panel section-gap">
        <div className="panel-head">
          <div>
            <h2>Network reading guide</h2>
            <p>Help the evaluator understand what is causal versus contextual.</p>
          </div>
        </div>

        <div className="panel-body grid grid-3">
          <div>
            <h3>1. Disruption source</h3>
            <p className="body-copy">
              Primary supplier SUP-01 is unavailable during the configured blackout period. All order attempts
              directed to it during this window fail constraint checks.
            </p>
          </div>
          <div>
            <h3>2. Propagation</h3>
            <p className="body-copy">
              Components feed PROD-01 (FAC-01) and PROD-02 (FAC-02). Finished assemblies stock DC-01 and DC-02.
              When stock depletes, customer orders go unfulfilled under lost-service rules.
            </p>
          </div>
          <div>
            <h3>3. Limits of the model</h3>
            <p className="body-copy">
              Upstream supplier blackout, lead time, unit cost, and daily capacity are strictly enforced.
              Downstream transfer rates and plant conversion limits are structural metadata only.
            </p>
          </div>
        </div>
      </section>

      <div className="footnote">
        <span>Topology source: deterministic network model</span>
        <span>Decision-support mode · no live purchasing connections</span>
      </div>
    </section>
  );
};
