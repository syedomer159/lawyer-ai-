import { pageImageUrl, type Document } from '../api/client'
import { usePage } from '../api/hooks'
import type { Selection } from '../pages/CaseWorkspace'

type Props = { caseId: string; doc: Document; selection: Selection; onChange: (s: Selection) => void }

export default function PageViewer({ caseId, doc, selection, onChange }: Props) {
  const { page, bbox, chunkId } = selection
  const detail = usePage(caseId, doc.id, page)
  const goTo = (p: number) => onChange({ docId: doc.id, page: p })

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2 text-sm">
        <span className="truncate font-medium">{doc.filename}</span>
        <div className="flex items-center gap-2 text-xs text-stone-600">
          {detail.data?.ocr && <span className="rounded bg-sky-100 px-1.5 py-0.5 text-sky-800">OCR</span>}
          <button disabled={page <= 1} onClick={() => goTo(page - 1)} className="px-1 disabled:opacity-30">
            ‹
          </button>
          <span>
            page {page} / {doc.n_pages}
          </span>
          <button disabled={page >= doc.n_pages} onClick={() => goTo(page + 1)} className="px-1 disabled:opacity-30">
            ›
          </button>
        </div>
      </div>

      {doc.kind === 'text' ? (
        <div className="space-y-2 p-4">
          {detail.data?.chunks.map((c) => (
            <p key={c.id} className={`whitespace-pre-wrap rounded p-2 text-sm ${
              c.id === chunkId ? 'bg-yellow-100 ring-2 ring-yellow-400' : ''}`}>
              {c.text}
            </p>
          ))}
        </div>
      ) : (
        <div className="mx-auto max-w-3xl p-3">
          {/* The wrapper is exactly the image's size, so bbox fractions map to percentages. */}
          <div className="relative">
            <img src={pageImageUrl(caseId, doc.id, page)} alt={`${doc.filename} page ${page}`}
              className="block w-full" />
            {bbox && (
              <div
                className="pointer-events-none absolute border-2 border-yellow-400 bg-yellow-300/30"
                style={{
                  left: `${bbox[0] * 100}%`,
                  top: `${bbox[1] * 100}%`,
                  width: `${(bbox[2] - bbox[0]) * 100}%`,
                  height: `${(bbox[3] - bbox[1]) * 100}%`,
                }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
