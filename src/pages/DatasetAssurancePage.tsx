import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ChevronRight,
  Copy,
  Database,
  ExternalLink,
  FileText,
  FileType,
  Image as ImageIcon,
  LayoutGrid,
  ScanSearch,
  ShieldAlert,
  Target,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DatasetAssuranceData, DriftPoint, RiskLevel } from '../types';
import { PageHeader } from '../components/PageHeader';
import { FileCard } from '../components/FileCard';
import { EvidenceThumb } from '../components/EvidenceThumb';
import { Card, CardTitle } from '../components/ui/Card';
import { Chip, riskTone } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Gauge } from '../components/ui/Gauge';
import { analyzeDataset, getDatasetDetail, uploadDataset } from '../lib/backend';
import { UploadDatasetModal } from '../components/UploadDatasetModal';

const overviewIcons = [ImageIcon, LayoutGrid, Users, FileType];

const anomalyIcons: Record<string, typeof AlertTriangle> = {
  alert: AlertTriangle,
  copy: Copy,
  target: Target,
  scan: ScanSearch,
};

type TabId = 'feature' | 'class' | 'domain';

const TABS: { id: TabId; label: string }[] = [
  { id: 'feature', label: 'Feature Drift' },
  { id: 'class', label: 'Class Drift' },
  { id: 'domain', label: 'Domain Drift' },
];

function formatBytes(bytes?: number) {
  if (!bytes || bytes <= 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function formatDate(value?: string | null) {
  if (!value) return 'Just now';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function statusFromState(state?: string | null) {
  switch (state?.toUpperCase()) {
    case 'UPLOADED':
      return 'Uploaded';
    case 'ANALYSING':
      return 'Analyzing';
    case 'ANALYSED':
      return 'Processed';
    default:
      return 'Processed';
  }
}

function mapRiskLevel(level?: string | null): RiskLevel {
  switch (level?.toUpperCase()) {
    case 'CRITICAL':
      return 'critical';
    case 'HIGH':
      return 'high';
    case 'MEDIUM':
      return 'medium';
    default:
      return 'low';
  }
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
}

function buildDatasetDashboard(detail: {
  dataset?: {
    id?: string;
    name?: string;
    format?: string;
    sizeBytes?: number;
    uploadedAt?: string;
    imageCount?: number | null;
    classCount?: number | null;
  };
  latestAnalysis?: {
    status?: string | null;
    trustScore?: number | string | null;
    riskLevel?: string | null;
    duplicatesCount?: number | null;
    floodCount?: number | null;
    labelFlipCount?: number | null;
    systematicMislabelCount?: number | null;
    triggerCount?: number | null;
    oodCount?: number | null;
    contributorRisks?: Array<{
      contributor?: string | null;
      riskLevel?: string | null;
      riskScore?: number | string | null;
    }> | null;
    evidence?: Array<{
      title?: string | null;
      severity?: string | null;
      description?: string | null;
    }> | null;
  } | null;
} | null): DatasetAssuranceData | null {
  if (!detail?.dataset) {
    return null;
  }

  const dataset = detail.dataset;
  const analysis = detail.latestAnalysis;
  const totalImages = Number(dataset.imageCount ?? 0);
  const classCount = Number(dataset.classCount ?? 0);
  const contributors = analysis?.contributorRisks ?? [];
  const duplicateImages = Number(analysis?.duplicatesCount ?? 0);
  const suspiciousSamples = [
    Number(analysis?.duplicatesCount ?? 0),
    Number(analysis?.floodCount ?? 0),
    Number(analysis?.labelFlipCount ?? 0),
    Number(analysis?.systematicMislabelCount ?? 0),
    Number(analysis?.triggerCount ?? 0),
    Number(analysis?.oodCount ?? 0),
  ].reduce((total, value) => total + value, 0);

  const trustScore = Number(analysis?.trustScore ?? 0);
  const summaryPercent = clampPercent(trustScore);

  return {
    file: {
      name: dataset.name || 'Uploaded dataset',
      meta: `${totalImages.toLocaleString()} images · ${formatBytes(dataset.sizeBytes)} · ${dataset.format || 'ZIP'}`,
      status: statusFromState(analysis?.status || 'ANALYSED'),
      timestamp: formatDate(dataset.uploadedAt),
    },
    overview: [
      { label: 'Total Images', value: totalImages.toLocaleString() },
      { label: 'Classes', value: String(classCount) },
      { label: 'Contributors', value: String(contributors.length) },
      { label: 'Image Formats', value: dataset.format || 'ZIP' },
      { label: 'Duplicate Images', value: String(duplicateImages) },
      { label: 'Corrupted Images', value: '0' },
      { label: 'Missing Labels', value: '0' },
      { label: 'Suspicious Samples', value: String(suspiciousSamples) },
    ],
    quality: [
      { label: 'Duplicate Images', count: String(duplicateImages), percent: clampPercent(duplicateImages * 8) },
      { label: 'Corrupted Images', count: '0', percent: 0 },
      { label: 'Missing Labels', count: '0', percent: 0 },
      { label: 'Suspicious Samples', count: String(suspiciousSamples), percent: clampPercent(suspiciousSamples * 10) },
    ],
    featureDrift: [],
    classDrift: [],
    domainDrift: [],
    contributors: contributors.map((entry) => ({
      name: entry.contributor || 'Contributor',
      level: mapRiskLevel(entry.riskLevel),
    })),
    anomalies: (analysis?.evidence ?? []).slice(0, 5).map((entry, index) => ({
      name: entry.title || `Finding ${index + 1}`,
      level: mapRiskLevel(entry.severity),
      icon: index % 2 === 0 ? 'alert' : 'scan',
    })),
    evidence: (analysis?.evidence ?? []).slice(0, 4).map((entry, index) => ({
      scene: ['tank', 'truck', 'plane', 'snow'][index % 4] as 'tank' | 'truck' | 'plane' | 'snow',
      chip: [entry.title || 'Finding', entry.severity || 'medium'],
    })),
    summary: {
      percent: summaryPercent,
      label: analysis?.riskLevel ? analysis.riskLevel.toUpperCase() : 'VERIFIED',
      status: analysis?.riskLevel ? analysis.riskLevel.toLowerCase() : 'ready',
    },
  };
}

function DistributionCard({ data }: { data: DatasetAssuranceData }) {
  const [tabId, setTabId] = useState<TabId>('feature');
  const active = TABS.find((tab) => tab.id === tabId) ?? TABS[0];
  const isHistogram = tabId === 'feature';
  const tabData: Record<TabId, DriftPoint[]> = {
    feature: data.featureDrift,
    class: data.classDrift,
    domain: data.domainDrift,
  };

  return (
    <Card className="p-5">
      <CardTitle className="mb-4">Distribution Analysis</CardTitle>
      <div className="mb-3 inline-flex rounded-lg bg-slate-100 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setTabId(tab.id)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              tab.id === tabId ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="h-[212px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={tabData[tabId]} barGap={1} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#eef1f5" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              tickLine={false}
              axisLine={{ stroke: '#e2e8f0' }}
              interval={isHistogram ? 3 : 0}
            />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={30} />
            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: '1px solid #e2e8f0',
                boxShadow: '0 4px 12px rgba(15, 23, 42, 0.08)',
                fontSize: 12,
                padding: '6px 10px',
              }}
              cursor={{ fill: 'rgba(148, 163, 184, 0.1)' }}
              labelFormatter={(label) => (isHistogram ? `Feature value ${label}` : String(label))}
            />
            <Legend
              iconType="circle"
              iconSize={7}
              align="right"
              verticalAlign="top"
              wrapperStyle={{ fontSize: 11, paddingBottom: 6 }}
            />
            <Bar dataKey="reference" name="Reference" fill="#cbd5e1" radius={[2, 2, 0, 0]} maxBarSize={isHistogram ? 10 : 26} />
            <Bar dataKey="uploaded" name="Uploaded" fill="#4a7dd8" radius={[2, 2, 0, 0]} maxBarSize={isHistogram ? 10 : 26} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-right text-[10px] text-slate-400">
        {active.label} — reference baseline vs uploaded dataset
      </p>
    </Card>
  );
}

export function DatasetAssurancePage() {
  const [data, setData] = useState<DatasetAssuranceData | null>(null);
  const [backendReady, setBackendReady] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const handleUpload = async (file: File, datasetName: string) => {
    if (!file) {
      setError('Please select a valid dataset file.');
      return;
    }

    setError(null);
    setUploading(true);
    setProcessing(false);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', datasetName || file.name);
    formData.append('codename', datasetName || file.name);
    formData.append('format', 'COCO');
    formData.append('classification', 'UNCLASSIFIED');
    formData.append('notes', `Uploaded via TRUSTVISION UI at ${new Date().toISOString()}`);

    try {
      const uploadResponse = await uploadDataset(formData);
      const datasetId = uploadResponse?.id;

      setUploading(false);
      setProcessing(true);
      setToast('Uploading dataset...');
      if (!datasetId) {
        setProcessing(false);
        throw new Error('The backend did not return a valid dataset identifier.');
      }

      const analysisResponse = await analyzeDataset(datasetId);
      const detail = await getDatasetDetail(datasetId);
      const dashboard = buildDatasetDashboard(detail ?? { dataset: { ...uploadResponse }, latestAnalysis: analysisResponse });
      setData(dashboard);
      setProcessing(false);
      setModalOpen(false);
      setBackendReady(true);
      setToast('Dataset analyzed successfully');
    } catch (uploadError) {
      setUploading(false);
      setProcessing(false);
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : 'An unexpected error occurred while uploading the dataset.',
      );
      setToast('Upload failed');
    }
  };

  const emptyState = (
    <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-600">
        <Database size={28} />
      </div>
      <h3 className="mt-5 text-2xl font-semibold text-slate-800">No Dataset Uploaded</h3>
      <p className="mt-2 text-sm text-slate-500">Upload a dataset to begin Dataset Assurance analysis.</p>
      <div className="mt-6 flex justify-center">
        <Button onClick={() => setModalOpen(true)}>Upload Dataset</Button>
      </div>
    </div>
  );

  return (
    <div>
      <UploadDatasetModal
        open={modalOpen}
        uploading={uploading}
        processing={processing}
        error={error}
        onClose={() => {
          if (uploading || processing) return;
          setModalOpen(false);
          setError(null);
        }}
        onUpload={handleUpload}
      />

      {toast ? (
        <div className="fixed right-5 top-5 z-[60] rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700 shadow-lg">
          {toast}
        </div>
      ) : null}

      <PageHeader
        title="Dataset Assurance"
        subtitle="Analyze, verify and detect risks in multi-contributor datasets."
      >
        {data ? (
          <FileCard
            icon={<Database size={19} />}
            name={data.file.name}
            meta={data.file.meta}
            status={backendReady ? 'Backend live' : data.file.status}
            timestamp={data.file.timestamp}
            onUploadClick={() => {
              setError(null);
              setModalOpen(true);
            }}
            disabled={uploading || processing}
          />
        ) : (
          <Button onClick={() => setModalOpen(true)} disabled={uploading || processing}>
            <Database size={15} />
            Upload Dataset
          </Button>
        )}
      </PageHeader>

      {!data ? (
        emptyState
      ) : (
        <>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-[2.7fr_3.3fr_3.8fr_2.3fr]">
            <Card className="p-5">
              <CardTitle className="mb-4">Dataset Overview</CardTitle>
              <div className="grid grid-cols-2 gap-x-3 gap-y-5">
                {data.overview.map((item, index) => {
                  const Icon = overviewIcons[index % overviewIcons.length];
                  return (
                    <div key={item.label} className="flex items-start gap-2">
                      <Icon size={15} className="mt-0.5 shrink-0 text-slate-400" />
                      <div className="min-w-0">
                        <p className="whitespace-nowrap text-xs text-slate-500">{item.label}</p>
                        <p className="mt-0.5 whitespace-nowrap text-[15px] font-bold leading-snug text-slate-800">
                          {item.value}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card className="flex flex-col p-5">
              <CardTitle className="mb-4">Data Quality Analysis</CardTitle>
              <div className="grid flex-1 content-center grid-cols-2 gap-y-5 sm:grid-cols-4">
                {data.quality.map((metric) => (
                  <div key={metric.label} className="flex flex-col items-center gap-2 text-center">
                    <Gauge percent={metric.percent} tone="red" size={62} stroke={7} />
                    <div>
                      <p className="text-sm font-bold text-slate-800">{metric.count}</p>
                      <p className="text-[11px] leading-tight text-slate-500">{metric.label}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <DistributionCard data={data} />

            <Card className="p-5">
              <CardTitle className="mb-2">Contributor Risk</CardTitle>
              <ul className="divide-y divide-slate-100">
                {data.contributors.map((contributor) => (
                  <li key={contributor.name}>
                    <button type="button" className="flex w-full items-center justify-between gap-3 py-3 text-left">
                      <span className="text-sm font-medium text-slate-700">{contributor.name}</span>
                      <span className="flex items-center gap-2">
                        <Chip tone={riskTone[contributor.level]} className="capitalize">
                          {contributor.level}
                        </Chip>
                        <ChevronRight size={14} className="text-slate-300" />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-[3fr_4.9fr_2.3fr_1.9fr]">
            <Card className="p-5">
              <CardTitle className="mb-2">Anomaly Assessment</CardTitle>
              <ul className="divide-y divide-slate-100">
                {data.anomalies.map((anomaly) => {
                  const Icon = anomalyIcons[anomaly.icon] ?? AlertTriangle;
                  return (
                    <li key={anomaly.name}>
                      <button type="button" className="flex w-full items-center justify-between gap-3 py-3.5 text-left">
                        <span className="flex items-center gap-3">
                          <Icon size={16} className="shrink-0 text-slate-500" />
                          <span className="text-sm font-medium text-slate-700">{anomaly.name}</span>
                        </span>
                        <span className="flex items-center gap-2">
                          <Chip tone={riskTone[anomaly.level]} className="capitalize">
                            {anomaly.level}
                          </Chip>
                          <ChevronRight size={14} className="text-slate-300" />
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </Card>

            <Card className="p-5">
              <CardTitle className="mb-4">Evidence Preview</CardTitle>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {data.evidence.map((sample) => (
                  <div
                    key={sample.scene + sample.chip[0]}
                    className="relative overflow-hidden rounded-lg border border-slate-200"
                  >
                    <EvidenceThumb scene={sample.scene} className="aspect-[4/3] w-full" />
                    <div className="absolute bottom-1.5 left-1.5 rounded-md bg-red-100/95 px-1.5 py-1 text-[10px] font-medium leading-tight text-red-700">
                      {sample.chip.map((line) => (
                        <span key={line} className="block">
                          {line}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="flex flex-col p-5">
              <CardTitle className="mb-4">Assurance Summary</CardTitle>
              <div className="flex flex-1 flex-col items-center justify-center text-center">
                <Gauge percent={data.summary.percent} tone="amber" size={104} stroke={10} />
                <p className="mt-3 text-sm font-semibold text-slate-800">{data.summary.label}</p>
                <Chip tone="amber" className="mt-2">
                  {data.summary.status}
                </Chip>
              </div>
            </Card>

            <div className="flex flex-col gap-3 lg:col-span-2 xl:col-span-1 xl:pt-1">
              <Button>
                <FileText size={15} />
                Generate Report
              </Button>
              <Button variant="secondary">
                <ExternalLink size={15} />
                View Full Analysis
              </Button>
              <Button variant="danger">
                <ShieldAlert size={15} />
                Quarantine Dataset
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
