import { useEffect, useState } from 'react';
import { Copy, FileText, Image as ImageIcon, TriangleAlert } from 'lucide-react';
import inferenceJson from '../data/inference.json';
import type { InferenceAssuranceData } from '../types';
import { PageHeader } from '../components/PageHeader';
import { FileCard } from '../components/FileCard';
import { EvidenceThumb } from '../components/EvidenceThumb';
import { Card, CardTitle } from '../components/ui/Card';
import { Chip } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Gauge } from '../components/ui/Gauge';
import { ProgressBar } from '../components/ui/ProgressBar';
import { getJson } from '../lib/backend';

const FALLBACK_DATA = inferenceJson as InferenceAssuranceData;

export function InferenceAssurancePage() {
  const [data, setData] = useState<InferenceAssuranceData>(FALLBACK_DATA);
  const [backendReady, setBackendReady] = useState(false);

  useEffect(() => {
    const load = async () => {
      const live = await getJson<InferenceAssuranceData>('/inference/provenance/00000000-0000-0000-0000-000000000001');
      setBackendReady(Boolean(live));
      if (live) {
        setData(live);
      }
    };

    void load();
  }, []);

  return (
    <div>
      <PageHeader
        title="Inference Assurance"
        subtitle="Verify inference outputs with cryptographic provenance and detect manipulations."
      >
        <FileCard
          icon={
            <EvidenceThumb scene={data.file.scene ?? 'tank'} className="h-full w-full object-cover" />
          }
          name={data.file.name}
          meta={data.file.meta}
          status={backendReady ? 'Backend live' : data.file.status}
          timestamp={data.file.timestamp}
        />
      </PageHeader>

      {/* Row 1 */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-[2.8fr_3fr_2.6fr]">
        <Card className="p-5">
          <CardTitle className="mb-4">Input & Prediction</CardTitle>
          <div className="flex gap-4">
            <span className="block h-32 w-40 shrink-0 overflow-hidden rounded-lg border border-slate-200">
              <EvidenceThumb scene="tank" className="h-full w-full" />
            </span>
            <div className="min-w-0 flex-1 space-y-3">
              <div>
                <p className="text-xs text-slate-500">Prediction</p>
                <p className="text-lg font-bold text-slate-800">{data.prediction.label}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Confidence</p>
                <p className="text-sm font-bold text-slate-800">{data.prediction.confidence}%</p>
                <ProgressBar value={data.prediction.confidence} className="mt-1 max-w-[180px]" />
              </div>
              <div>
                <p className="text-xs text-slate-500">Timestamp</p>
                <p className="text-sm font-medium text-slate-700">{data.prediction.timestamp}</p>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <CardTitle className="mb-2">Provenance Verification</CardTitle>
          <ul className="divide-y divide-slate-100">
            {data.provenance.map((row) => (
              <li key={row.label} className="flex items-center justify-between gap-3 py-2.5">
                <span className="text-xs text-slate-500">{row.label}</span>
                {row.copyable ? (
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-xs text-slate-700">{row.value}</span>
                    <button
                      type="button"
                      aria-label={`Copy ${row.label}`}
                      onClick={() => void navigator.clipboard.writeText(row.value)}
                      className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                    >
                      <Copy size={13} />
                    </button>
                  </span>
                ) : (
                  <Chip tone="green">{row.value}</Chip>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          <CardTitle className="mb-2">Integrity Checks</CardTitle>
          <ul className="divide-y divide-slate-100">
            {data.integrity.map((row) => (
              <li key={row.label} className="flex items-center justify-between gap-3 py-3">
                <span className="text-sm text-slate-700">{row.label}</span>
                <Chip tone="green">{row.value}</Chip>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Row 2 */}
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-[2fr_1fr]">
        <Card className="flex flex-col p-5 sm:flex-row sm:items-center sm:gap-8">
          <div className="flex items-center gap-6">
            <Gauge percent={data.summary.percent} tone="green" size={110} stroke={10} />
            <div>
              <p className="text-sm font-semibold text-slate-800">{data.summary.label}</p>
              <Chip tone="green" className="mt-2">
                {data.summary.status}
              </Chip>
            </div>
          </div>
          <div className="mt-5 flex-1 border-t border-slate-100 pt-5 sm:ml-auto sm:mt-0 sm:max-w-xs sm:border-l sm:border-t-0 sm:pl-8 sm:pt-0">
            <p className="text-xs leading-relaxed text-slate-500">
              Cryptographic provenance and integrity checks all passed for this inference output.
            </p>
          </div>
        </Card>

        <div className="flex flex-col gap-3 xl:pt-1">
          <Button>
            <FileText size={15} />
            Generate Report
          </Button>
          <Button variant="secondary">
            <ImageIcon size={15} />
            View Evidence
          </Button>
          <Button variant="danger">
            <TriangleAlert size={15} />
            Flag For Review
          </Button>
        </div>
      </div>
    </div>
  );
}
