import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { AuditReportsPage } from './pages/AuditReportsPage';
import { DashboardPage } from './pages/DashboardPage';
import { DatasetAssurancePage } from './pages/DatasetAssurancePage';
import { InferenceAssurancePage } from './pages/InferenceAssurancePage';
import { ModelAssurancePage } from './pages/ModelAssurancePage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="assurance/datasets" element={<DatasetAssurancePage />} />
          <Route path="assurance/models" element={<ModelAssurancePage />} />
          <Route path="assurance/inference" element={<InferenceAssurancePage />} />
          <Route path="audit/reports" element={<AuditReportsPage />} />
          <Route path="*" element={<DashboardPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
