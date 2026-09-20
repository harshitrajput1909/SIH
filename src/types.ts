export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type EvidenceScene = 'tank' | 'truck' | 'plane' | 'snow';

export interface FileMeta {
  name: string;
  meta: string;
  status: string;
  timestamp: string;
  scene?: EvidenceScene;
}

export interface DriftPoint {
  label: string;
  reference: number;
  uploaded: number;
}

export interface DatasetAssuranceData {
  file: FileMeta;
  overview: { label: string; value: string }[];
  quality: { label: string; count: string; percent: number }[];
  featureDrift: DriftPoint[];
  classDrift: DriftPoint[];
  domainDrift: DriftPoint[];
  contributors: { name: string; level: RiskLevel }[];
  anomalies: { name: string; level: RiskLevel; icon: string }[];
  evidence: { scene: EvidenceScene; chip: string[] }[];
  summary: { percent: number; label: string; status: string };
}

export interface ModelAssuranceData {
  file: FileMeta;
  overview: { label: string; value: string }[];
  risks: { label: string; level: RiskLevel; icon: string }[];
  trainingRisk: { label: string; level: RiskLevel }[];
  summary: { percent: number; label: string; status: string };
}

export interface InferenceAssuranceData {
  file: FileMeta;
  prediction: { label: string; confidence: number; timestamp: string };
  provenance: { label: string; value: string; copyable?: boolean }[];
  integrity: { label: string; value: string }[];
  summary: { percent: number; label: string; status: string };
}

export interface DashboardData {
  kpis: { label: string; value: string; sub: string }[];
  recent: {
    name: string;
    type: string;
    score: number;
    status: string;
    tone: 'green' | 'amber' | 'red';
    date: string;
  }[];
}

export interface AuditData {
  entries: {
    timestamp: string;
    actor: string;
    action: string;
    target: string;
    status: string;
  }[];
}
