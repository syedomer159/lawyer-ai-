import type { CitationData } from '../api/hooks'
import type { Selection } from '../pages/CaseWorkspace'

/** A clickable source reference. Unverified quotes (not found in the cited text) are flagged. */
export default function CitationChip({ citation, onOpen }: { citation: CitationData; onOpen: (s: Selection) => void }) {
  const { ref, quote, verified } = citation
  return (
    <button
      title={verified ? `“${quote}”` : `Not found in the document text: “${quote}”`}
      onClick={() => onOpen({ docId: ref.doc_id, page: ref.page, chunkId: ref.chunk_id, bbox: ref.bbox })}
      className={`inline-flex max-w-full items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] ${
        verified
          ? 'border-stone-300 bg-white text-stone-700 hover:bg-stone-100'
          : 'border-amber-400 bg-amber-50 text-amber-800'
      }`}
    >
      <span className="truncate">
        {ref.filename} · p{ref.page}
      </span>
      {!verified && <span className="font-semibold">unverified</span>}
    </button>
  )
}
