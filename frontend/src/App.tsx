import React from 'react';
import { Toast } from './components/common/Toast';
import { Sidebar } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { ScenarioProvider } from './context/ScenarioContext';
import { useScenario } from './context/useScenario';
import { CommandCenter } from './pages/CommandCenter';
import { RecoveryWorkspace } from './pages/RecoveryWorkspace';
import { ScenarioLab } from './pages/ScenarioLab';
import { StrategyBenchmark } from './pages/StrategyBenchmark';
import { SupplierCapacity } from './pages/SupplierCapacity';
import { SupplyNetwork } from './pages/SupplyNetwork';

const MainContent: React.FC = () => {
  const { page, apiError } = useScenario();

  return (
    <div className="main-wrap">
      <TopBar />
      <main className="content">
        {apiError && (
          <div className="warning-note" style={{ marginBottom: '16px' }}>
            <strong>API Alert:</strong> {apiError}. Currently operating in verified reference snapshot mode.
          </div>
        )}

        {page === 'command' && <CommandCenter />}
        {page === 'scenario' && <ScenarioLab />}
        {page === 'network' && <SupplyNetwork />}
        {page === 'sourcing' && <SupplierCapacity />}
        {page === 'recovery' && <RecoveryWorkspace />}
        {page === 'benchmark' && <StrategyBenchmark />}
      </main>
      <Toast />
    </div>
  );
};

export function App() {
  return (
    <ScenarioProvider>
      <div className="app">
        <Sidebar />
        <MainContent />
      </div>
    </ScenarioProvider>
  );
}

export default App;
