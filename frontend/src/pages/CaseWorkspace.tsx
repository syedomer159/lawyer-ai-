import { useState } from 'react'
import { useParams } from 'react-router'
import type { BBox, Document } from '../api/client'
import { useCase, useDocuments, useUsage } from '../api/hooks'
import AnalysisPanel from '../components/AnalysisPanel'
import CourtroomPanel from '../components/CourtroomPanel'
import ArgumentsPanel from '../components/ArgumentsPanel'
import AssistantPanel from '../components/AssistantPanel'
import DocumentPanel from '../components/DocumentPanel'
import PageViewer from '../components/PageViewer'
import SearchPanel from '../components/SearchPanel'

/** What the viewer shows: a page, optionally with one cited region highlighted. */
export type Selection = { docId: string; page: number; chunkId?: number; bbox?: BBox | null }

const TABS = ['Documents', 'Analysis', 'Arguments', 'Courtroom', 'Ask'] as const
type Tab = (typeof TABS)[number]

export default function CaseWorkspace() {
  const { caseId = '' } = useParams()
  const kase = useCase(caseId)
  const docs = useDocuments(caseId)
  const usage = useUsage(caseId)
  const [tab, setTab] = useState<Tab>('Documents')
  const [selection, setSelection] = useState<Selection | null>(null)
  const selectedDoc: Document | undefined = docs.data?.find((d) => d.id === selection?.docId)

  if (kase.isError) return <p className="p-6 text-sm text-red-600">{kase.error.message}</p>
  return (
    <main className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="min-w-0 space-y-4">
        <div>
          <h1 className="text-lg font-semibold">{kase.data?.title ?? '…'}</h1>
          <p className="text-xs text-stone-500">
            {kase.data && `Client ${kase.data.client} · ${kase.data.user_side} · ${kase.data.charges.join(', ')}`}
          </p>
          {usage.data && (
            <p className="text-xs text-stone-400" title="Every call is traced in Phoenix (project lawyer-ai)">
              AI usage: {usage.data.calls} calls · {usage.data.input_tokens + usage.data.output_tokens} tokens · $
              {usage.data.cost_usd.toFixed(4)}
            </p>
          )}
        </div>
        <nav className="flex gap-1 border-b border-stone-200">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`-mb-px border-b-2 px-3 py-1.5 text-sm ${
                t === tab ? 'border-stone-900 font-medium' : 'border-transparent text-stone-500 hover:text-stone-800'
              }`}
            >
              {t}
            </button>
          ))}
        </nav>
        {tab === 'Documents' && (
          <>
            <DocumentPanel caseId={caseId} docs={docs.data ?? []} selectedId={selection?.docId}
              onOpen={(doc) => setSelection({ docId: doc.id, page: 1 })} />
            <SearchPanel caseId={caseId} onOpen={setSelection} />
          </>
        )}
        {tab === 'Analysis' && <AnalysisPanel caseId={caseId} onOpen={setSelection} />}
        {tab === 'Arguments' && <ArgumentsPanel caseId={caseId} onOpen={setSelection} />}
        {tab === 'Courtroom' && <CourtroomPanel caseId={caseId} />}
        {tab === 'Ask' && <AssistantPanel caseId={caseId} onOpen={setSelection} />}
      </section>
      <section className="min-w-0 lg:sticky lg:top-4 lg:self-start">
        {selection && selectedDoc ? (
          <PageViewer caseId={caseId} doc={selectedDoc} selection={selection} onChange={setSelection} />
        ) : (
          <div className="grid h-96 place-items-center rounded-lg border border-dashed border-stone-300 p-4 text-center text-sm text-stone-500">
            Open a document, a search result, or any citation to see the source page here.
          </div>
        )}
      </section>
    </main>
  )
}
