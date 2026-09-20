import { ChevronRight } from 'lucide-react';
import dashboardJson from '../data/dashboard.json';
import type { DashboardData } from '../types';
import { PageHeader } from '../components/PageHeader';
import { Card, CardTitle } from '../components/ui/Card';
import { Chip } from '../components/ui/Badge';

const data = dashboardJson as DashboardData;

export function DashboardPage() {
  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Fleet-wide AI integrity assurance overview." />

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {data.kpis.map((kpi) => (
          <Card key={kpi.label} className="p-5">
            <p className="text-xs text-slate-500">{kpi.label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-800">{kpi.value}</p>
            <p className="mt-1 text-xs text-slate-500">{kpi.sub}</p>
          </Card>
        ))}
      </div>

      <Card className="mt-5 p-5">
        <CardTitle className="mb-2">Recent Assessments</CardTitle>
        <ul className="divide-y divide-slate-100">
          {data.recent.map((row) => (
            <li key={row.name}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-4 py-3 text-left"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800">{row.name}</p>
                  <p className="text-xs text-slate-500">
                    {row.type} · {row.date}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <span className="text-sm font-bold text-slate-800">{row.score}%</span>
                  <Chip tone={row.tone}>{row.status}</Chip>
                  <ChevronRight size={14} className="hidden text-slate-300 sm:block" />
                </div>
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
