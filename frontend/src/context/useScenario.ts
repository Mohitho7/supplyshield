import { useContext } from 'react';
import { ScenarioContext, type ScenarioContextType } from './ScenarioContextDefinition';

export const useScenario = (): ScenarioContextType => {
  const context = useContext(ScenarioContext);
  if (!context) {
    throw new Error('useScenario must be used within a ScenarioProvider');
  }
  return context;
};
