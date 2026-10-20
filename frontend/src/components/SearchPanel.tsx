import { useState, type FormEvent } from 'react'
import { useSearch } from '../api/hooks'
import type { Selection } from '../pages/CaseWorkspace'

export default function SearchPanel({ caseId, onOpen }: { caseId: string; onOpen: (s: Selection) => void }) {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const results = useSearch(caseId, query)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setQuery(draft)
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <form onSubmit={submit} className="flex gap-2 border-b border-stone-200 p-2">
        <input
          className="min-w-0 flex-1 rounded-md border border-stone-300 px-2 py-1 text-sm"
          placeholder="Search this case, e.g. time of incident"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button className="rounded-md border border-stone-300 px-3 text-sm">Search</button>
      </form>
      {results.isFetching && <p className="px-3 py-2 text-xs text-stone-500">Searching…</p>}
      {results.isError && <p className="px-3 py-2 text-xs text-red-600">{results.error.message}</p>}
      {results.data?.length === 0 && <p className="px-3 py-2 text-xs text-stone-500">No matches.</p>}
      <ul className="max-h-96 divide-y divide-stone-100 overflow-y-auto">
        {results.data?.map((hit) => (
          <li key={hit.ref.chunk_id}>
            <button
              className="w-full px-3 py-2 text-left hover:bg-stone-50"
              onClick={() =>
                onOpen({ docId: hit.ref.doc_id, page: hit.ref.page, chunkId: hit.ref.chunk_id, bbox: hit.ref.bbox })
              }
            >
              <div className="text-xs font-medium text-stone-700">
                {hit.ref.filename} · p{hit.ref.page}
              </div>
              <div className="line-clamp-3 text-xs text-stone-600">{hit.text}</div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
