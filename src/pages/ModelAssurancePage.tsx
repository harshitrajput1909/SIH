import { useState } from 'react';
import {
  Box,
  Check,
  Crosshair,
  ExternalLink,
  FileText,
  Gauge as GaugeIcon,
  Info,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import modelJson from '../data/model.json';
import type { ModelAssuranceData } from '../types';
import { PageHeader } from '../components/PageHeader';
import { FileCard } from '../components/FileCard';
import { Card, CardTitle } from '../components/ui/Card';
import { Chip, riskTone } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Gauge } from '../components/ui/Gauge';

const data = modelJson as ModelAssuranceData;

const riskIcons: Record<string, LucideIcon> = {
  crosshair: Crosshair,
  shield: ShieldAlert,
  trend: TrendingUp,
  gauge: GaugeIcon,
};

type AccessMode = 'white' | 'black';

export function ModelAssurancePage() {
  const [mode, setMode] = useState<AccessMode>('white');

  return (
    <div>
      <PageHeader
        title="Model Assurance"
        subtitle="Analyze model architecture, detect vulnerabilities and verify training integrity."
      >
        <FileCard
          icon={<Box size={19} />}
          name={data.file.name}
          meta={data.file.meta}
          status={data.file.status}
          timestamp={data.file.timestamp}
        />
      </PageHeader>

      {/* Row 1 */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-[2.4fr_2.8fr_2.4fr_2.4fr]">
        <Card className="p-5">
          <CardTitle className="mb-3">Model Overview</CardTitle>
          <dl className="divide-y divide-slate-100 text-sm">
            {data.overview.map((row) => (
              <div key={row.label} className="flex items-center justify-between gap-3 py-2.5">
                <dt className="text-slate-500">{row.label}</dt>
                <dd className="text-right font-medium text-slate-800">{row.value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card className="p-5">
          <CardTitle className="mb-2">Model Risk Analysis</CardTitle>
          <ul className="divide-y divide-slate-100">
            {data.risks.map((risk) => {
              const Icon = riskIcons[risk.icon] ?? ShieldAlert;
              return (
                <li key={risk.label} className="flex items-center justify-between gap-3 py-3">
                  <span className="flex items-center gap-2.5 text-sm text-slate-700">
                    <Icon size={16} className="shrink-0 text-slate-500" />
                    {risk.label}
                  </span>
                  <Chip tone={riskTone[risk.level]} className="capitalize">
                    {risk.level}
                  </Chip>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card className="flex flex-col p-5">
          <CardTitle className="mb-4">Access Mode</CardTitle>
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => setMode('white')}
              className={`rounded-md py-2 text-xs font-medium transition-colors ${
                mode === 'white' ? 'bg-navy-800 text-white' : 'text-slate-600 hover:text-slate-800'
              }`}
            >
              White-box
            </button>
            <button
              type="button"
              onClick={() => setMode('black')}
              className={`rounded-md py-2 text-xs font-medium transition-colors ${
                mode === 'black' ? 'bg-navy-800 text-white' : 'text-slate-600 hover:text-slate-800'
              }`}
            >
              Black-box
            </button>
          </div>
          <div className="mt-auto flex items-center gap-3 pt-6">
            {mode === 'white' ? (
              <>
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                  <Check size={20} />
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-800">Model Accessible</p>
                  <p className="text-xs text-slate-500">Full analysis enabled.</p>
                </div>
              </>
            ) : (
              <>
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-600">
                  <Info size={20} />
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-800">Limited Access</p>
                  <p className="text-xs text-slate-500">Behavioural analysis only.</p>
                </div>
              </>
            )}
          </div>
        </Card>

        <Card className="p-5">
          <CardTitle className="mb-2">Training Source Risk</CardTitle>
          <ul className="divide-y divide-slate-100">
            {data.trainingRisk.map((source) => (
              <li key={source.label} className="flex items-center justify-between gap-3 py-3">
                <span className="text-sm text-slate-700">{source.label}</span>
                <Chip tone={riskTone[source.level]} className="capitalize">
                  {source.level}
                </Chip>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Row 2 */}
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-[2fr_1fr]">
        <Card className="flex flex-col p-5 sm:flex-row sm:items-center sm:gap-8">
          <div className="flex items-center gap-6">
            <Gauge percent={data.summary.percent} tone="amber" size={110} stroke={10} />
            <div>
              <p className="text-sm font-semibold text-slate-800">{data.summary.label}</p>
              <Chip tone="amber" className="mt-2">
                {data.summary.status}
              </Chip>
            </div>
          </div>
          <div className="mt-5 flex-1 border-t border-slate-100 pt-5 sm:ml-auto sm:mt-0 sm:max-w-xs sm:border-l sm:border-t-0 sm:pl-8 sm:pt-0">
            <p className="text-xs leading-relaxed text-slate-500">
              Backdoor risk is the primary driver of this score. Review training sources before
              operational deployment.
            </p>
          </div>
        </Card>

        <div className="flex flex-col gap-3 xl:pt-1">
          <Button>
            <FileText size={15} />
            Generate Report
          </Button>
          <Button variant="secondary">
            <ExternalLink size={15} />
            View Detailed Analysis
          </Button>
          <Button variant="danger">
            <ShieldAlert size={15} />
            Quarantine Model
          </Button>
        </div>
      </div>
    </div>
  );
}
