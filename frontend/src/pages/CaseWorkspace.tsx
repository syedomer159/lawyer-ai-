import { useState } from 'react'
import { useParams } from 'react-router'
import type { BBox, Document } from '../api/client'
import { useCase, useDocuments, useUsage } from '../api/hooks'
import DocumentPanel from '../components/DocumentPanel'
import PageViewer from '../components/PageViewer'
import SearchPanel from '../components/SearchPanel'

/** What the viewer shows: a page, optionally with one cited region highlighted. */
export type Selection = { docId: string; page: number; chunkId?: number; bbox?: BBox | null }

export default function CaseWorkspace() {
  const { caseId = '' } = useParams()
  const kase = useCase(caseId)
  const docs = useDocuments(caseId)
  const usage = useUsage(caseId)
  const [selection, setSelection] = useState<Selection | null>(null)
  const selectedDoc: Document | undefined = docs.data?.find((d) => d.id === selection?.docId)

  if (kase.isError) return <p className="p-6 text-sm text-red-600">{kase.error.message}</p>
  return (
    <main className="grid gap-4 p-4 lg:grid-cols-[380px_1fr]">
      <aside className="space-y-4">
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
        <DocumentPanel caseId={caseId} docs={docs.data ?? []} selectedId={selection?.docId}
          onOpen={(doc) => setSelection({ docId: doc.id, page: 1 })} />
        <SearchPanel caseId={caseId} onOpen={setSelection} />
      </aside>
      <section className="min-w-0">
        {selection && selectedDoc ? (
          <PageViewer caseId={caseId} doc={selectedDoc} selection={selection} onChange={setSelection} />
        ) : (
          <div className="grid h-96 place-items-center rounded-lg border border-dashed border-stone-300 text-sm text-stone-500">
            Upload case files, then open a document or search the case.
          </div>
        )}
      </section>
    </main>
  )
}
