import auditJson from '../data/audit.json';
import type { AuditData } from '../types';
import { PageHeader } from '../components/PageHeader';
import { Card } from '../components/ui/Card';
import { Chip, type ChipTone } from '../components/ui/Badge';

const data = auditJson as AuditData;

const statusTones: Record<string, ChipTone> = {
  Trusted: 'green',
  Verified: 'green',
  Completed: 'slate',
  Actioned: 'sky',
};

export function AuditReportsPage() {
  return (
    <div>
      <PageHeader title="Audit & Reports" subtitle="Immutable record of all assurance actions." />

      <Card className="p-5">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2.5 pr-4 font-medium">Timestamp</th>
                <th className="py-2.5 pr-4 font-medium">Actor</th>
                <th className="py-2.5 pr-4 font-medium">Action</th>
                <th className="py-2.5 pr-4 font-medium">Target</th>
                <th className="py-2.5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.entries.map((entry) => (
                <tr key={`${entry.timestamp}-${entry.target}`} className="transition-colors hover:bg-slate-50/70">
                  <td className="py-3 pr-4 text-slate-500">{entry.timestamp}</td>
                  <td className="py-3 pr-4 text-slate-700">{entry.actor}</td>
                  <td className="py-3 pr-4 text-slate-700">{entry.action}</td>
                  <td className="py-3 pr-4 font-mono text-xs text-slate-600">{entry.target}</td>
                  <td className="py-3">
                    <Chip tone={statusTones[entry.status] ?? 'slate'}>{entry.status}</Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
