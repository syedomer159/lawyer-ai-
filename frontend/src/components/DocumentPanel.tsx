import type { Document } from '../api/client'
import { useUpload } from '../api/hooks'

const STATUS_STYLE: Record<Document['status'], string> = {
  queued: 'bg-stone-100 text-stone-600',
  processing: 'bg-amber-100 text-amber-800',
  ready: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-700',
}

type Props = {
  caseId: string
  docs: Document[]
  selectedId?: string
  onOpen: (doc: Document) => void
}

export default function DocumentPanel({ caseId, docs, selectedId, onOpen }: Props) {
  const upload = useUpload(caseId)

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2">
        <h2 className="text-sm font-semibold">Documents ({docs.length})</h2>
        <label className="cursor-pointer rounded-md bg-stone-900 px-3 py-1 text-xs text-white">
          {upload.isPending ? 'Uploading…' : 'Upload files'}
          <input
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.txt,.md"
            className="hidden"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? [])
              if (files.length) upload.mutate(files)
              e.target.value = ''
            }}
          />
        </label>
      </div>
      {upload.isError && <p className="px-3 py-2 text-xs text-red-600">{upload.error.message}</p>}
      <ul className="max-h-80 overflow-y-auto">
        {docs.map((d) => (
          <li key={d.id}>
            <button
              disabled={d.status !== 'ready'}
              onClick={() => onOpen(d)}
              title={d.error ?? undefined}
              className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-stone-50 disabled:cursor-default ${
                d.id === selectedId ? 'bg-stone-100' : ''
              }`}
            >
              <span className="truncate">{d.filename}</span>
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${STATUS_STYLE[d.status]}`}>
                {d.status === 'ready' ? `${d.n_pages} p` : d.status}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
