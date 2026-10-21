import { useState } from 'react'
import {
  useAnalysis,
  useSetConflictStatus,
  useStartAnalysis,
  type AnalysisData,
  type ConflictData,
  type ElementData,
} from '../api/hooks'
import type { Selection } from '../pages/CaseWorkspace'
import CitationChip from './CitationChip'

type Open = (s: Selection) => void

const SEVERITY = { high: 'bg-red-100 text-red-800', medium: 'bg-amber-100 text-amber-800', low: 'bg-stone-100 text-stone-600' }
const STATUS = { supported: 'bg-stone-100 text-stone-600', weak: 'bg-amber-100 text-amber-800', missing: 'bg-red-100 text-red-800' }

export function RunAnalysis({ caseId, analysis }: { caseId: string; analysis?: AnalysisData }) {
  const start = useStartAnalysis(caseId)
  const job = analysis?.job
  const running = job?.status === 'running'
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-stone-200 bg-white p-3">
      <button
        className="rounded-md bg-stone-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        disabled={running || start.isPending}
        onClick={() => start.mutate()}
      >
        {job ? 'Re-run analysis' : 'Analyse case'}
      </button>
      {running && (
        <div className="min-w-48 flex-1">
          <div className="text-xs text-stone-600">{job.step}…</div>
          <div className="mt-1 h-1.5 rounded bg-stone-200">
            <div className="h-1.5 rounded bg-stone-800" style={{ width: `${Math.round(job.progress * 100)}%` }} />
          </div>
        </div>
      )}
      {job?.status === 'done' && <span className="text-xs text-stone-500">Last run finished {job.finished_at} UTC</span>}
      {job?.status === 'failed' && <span className="text-xs text-red-600">Failed: {job.error}</span>}
      {start.isError && <span className="text-xs text-red-600">{start.error.message}</span>}
    </div>
  )
}

function ConflictCard({ caseId, conflict, onOpen }: { caseId: string; conflict: ConflictData; onOpen: Open }) {
  const setStatus = useSetConflictStatus(caseId)
  const dismissed = conflict.status === 'dismissed'
  return (
    <li className={`rounded-lg border border-stone-200 bg-white p-3 ${dismissed ? 'opacity-50' : ''}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold capitalize">{conflict.aspect}</span>
        <span className={`rounded px-1.5 py-0.5 ${SEVERITY[conflict.severity]}`}>{conflict.severity}</span>
        <span className={`rounded px-1.5 py-0.5 ${conflict.effect === 'helps' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
          {conflict.effect === 'helps' ? 'helps us' : 'hurts us'}
        </span>
        <span className="text-stone-400">{conflict.type.replace(/_/g, ' ')}</span>
        <button
          className="ml-auto text-stone-400 hover:text-stone-800"
          onClick={() => setStatus.mutate({ id: conflict.id, status: dismissed ? 'open' : 'dismissed' })}
        >
          {dismissed ? 'Restore' : 'Dismiss'}
        </button>
      </div>
      <p className="mt-1 text-sm">{conflict.explanation}</p>
      <ul className="mt-2 space-y-1">
        {conflict.claims.map((c) => (
          <li key={c.id} className="flex flex-wrap items-center gap-2 text-xs text-stone-600">
            <span className="font-medium text-stone-800">{c.speaker}:</span> {c.statement}
            <CitationChip citation={c.citation} onOpen={onOpen} />
          </li>
        ))}
      </ul>
    </li>
  )
}

function ElementList({ title, elements, onOpen }: { title: string; elements: ElementData[]; onOpen: Open }) {
  if (!elements.length) return null
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <ul className="space-y-2">
        {elements.map((e) => (
          <li key={e.id} className="rounded-lg border border-stone-200 bg-white p-3">
            <div className="flex items-start justify-between gap-2">
              <span className="text-sm font-medium">{e.element}</span>
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs ${STATUS[e.status]}`}>{e.status}</span>
            </div>
            <p className="mt-1 text-xs text-stone-600">{e.explanation}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {e.citations.map((c, i) => <CitationChip key={i} citation={c} onOpen={onOpen} />)}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function AnalysisPanel({ caseId, onOpen }: { caseId: string; onOpen: Open }) {
  const analysis = useAnalysis(caseId)
  const [showDismissed, setShowDismissed] = useState(false)
  const data = analysis.data
  const conflicts = (data?.conflicts ?? []).filter((c) => showDismissed || c.status === 'open')

  return (
    <div className="space-y-6">
      <RunAnalysis caseId={caseId} analysis={data} />
      {analysis.isError && <p className="text-sm text-red-600">{analysis.error.message}</p>}
      {data && data.conflicts.length + data.elements.length === 0 && data.job?.status !== 'running' && (
        <p className="text-sm text-stone-500">No analysis yet. Upload the case files, then run the analysis.</p>
      )}

      {data && data.conflicts.length > 0 && (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Contradictions ({conflicts.length})</h3>
            <label className="flex items-center gap-1 text-xs text-stone-500">
              <input type="checkbox" checked={showDismissed} onChange={(e) => setShowDismissed(e.target.checked)} />
              show dismissed
            </label>
          </div>
          <ul className="space-y-2">
            {conflicts.map((c) => <ConflictCard key={c.id} caseId={caseId} conflict={c} onOpen={onOpen} />)}
          </ul>
        </section>
      )}

      {data && (
        <>
          <ElementList title="What the prosecution must prove" onOpen={onOpen}
            elements={data.elements.filter((e) => e.kind === 'offence')} />
          <ElementList title="Investigation and procedure" onOpen={onOpen}
            elements={data.elements.filter((e) => e.kind === 'procedure')} />
        </>
      )}

      {data && data.adverse.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">What hurts our client</h3>
          <ul className="space-y-2">
            {data.adverse.map((a) => (
              <li key={a.id} className="rounded-lg border border-red-200 bg-white p-3">
                <p className="text-sm">{a.explanation}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {a.citations.map((c, i) => <CitationChip key={i} citation={c} onOpen={onOpen} />)}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data && data.timeline.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">Timeline (as each source tells it)</h3>
          <ol className="space-y-1 border-l border-stone-300 pl-3">
            {data.timeline.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono text-stone-500">{c.when?.replace('T', ' ')}</span>
                <span className="font-medium">{c.speaker}:</span>
                <span className="text-stone-600">{c.statement}</span>
                <CitationChip citation={c.citation} onOpen={onOpen} />
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}
