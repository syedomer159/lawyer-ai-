import { useAnalysis } from '../api/hooks'
import type { Selection } from '../pages/CaseWorkspace'
import { RunAnalysis } from './AnalysisPanel'
import CitationChip from './CitationChip'

export default function ArgumentsPanel({ caseId, onOpen }: { caseId: string; onOpen: (s: Selection) => void }) {
  const analysis = useAnalysis(caseId)
  const issues = analysis.data?.issues ?? []

  return (
    <div className="space-y-4">
      <RunAnalysis caseId={caseId} analysis={analysis.data} />
      {issues.length === 0 && <p className="text-sm text-stone-500">Arguments appear here after the analysis runs.</p>}
      {issues.map((issue) => (
        <article key={issue.id} className="space-y-3 rounded-lg border border-stone-200 bg-white p-4">
          <h3 className="font-semibold">{issue.title}</h3>
          <Block label="Our argument" text={issue.our_argument} tone="text-stone-900" />
          <Block label="They will say" text={issue.opposing_argument} tone="text-red-800" />
          <Block label="Our reply" text={issue.rebuttal} tone="text-emerald-800" />
          {issue.cross_questions.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">Cross-examination</div>
              <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-sm">
                {issue.cross_questions.map((q, i) => (
                  <li key={i}>
                    <span className="text-stone-500">{q.witness}:</span> {q.question}
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div className="flex flex-wrap gap-1">
            {issue.citations.map((c, i) => <CitationChip key={i} citation={c} onOpen={onOpen} />)}
          </div>
        </article>
      ))}
    </div>
  )
}

function Block({ label, text, tone }: { label: string; text: string; tone: string }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</div>
      <p className={`text-sm ${tone}`}>{text}</p>
    </div>
  )
}
