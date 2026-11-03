import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';

import { AnalysisProvider } from "./context/AnalysisContext";

createRoot(document.getElementById('root')).render(

  <StrictMode>

    <AnalysisProvider>

      <App />

    </AnalysisProvider>

  </StrictMode>

);