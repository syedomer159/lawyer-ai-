import { useState } from 'react'
import { useAsk, useAssistant } from '../api/hooks'
import type { Selection } from '../pages/CaseWorkspace'
import CitationChip from './CitationChip'

const EXAMPLES = ['What are the strongest contradictions in the prosecution case?', 'What time did the incident happen, according to each source?']

export default function AssistantPanel({ caseId, onOpen }: { caseId: string; onOpen: (s: Selection) => void }) {
  const messages = useAssistant(caseId)
  const ask = useAsk(caseId)
  const [text, setText] = useState('')
  const send = (q: string) => q.trim() && ask.mutate(q, { onSuccess: () => setText('') })

  return (
    <div className="space-y-3">
      <ol className="max-h-[32rem] space-y-3 overflow-y-auto">
        {messages.data?.length === 0 && (
          <li className="space-y-1 text-sm text-stone-500">
            <p>Ask anything about this case. Answers come only from the case files, with sources.</p>
            {EXAMPLES.map((e) => (
              <button key={e} className="block text-left text-xs text-stone-700 underline" onClick={() => send(e)}>{e}</button>
            ))}
          </li>
        )}
        {messages.data?.map((m) => (
          <li key={m.id} className={`rounded-lg p-3 text-sm ${m.role === 'user' ? 'bg-stone-100' : 'border border-stone-200 bg-white'}`}>
            <p className="whitespace-pre-wrap">{m.text}</p>
            {m.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {m.citations.map((c, i) => <CitationChip key={i} citation={c} onOpen={onOpen} />)}
              </div>
            )}
          </li>
        ))}
        {ask.isPending && <li className="text-xs text-stone-500">Searching the case files…</li>}
      </ol>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text) }}>
        <input className="min-w-0 flex-1 rounded-md border border-stone-300 px-2 py-1.5 text-sm" value={text}
          placeholder="Ask about this case…" onChange={(e) => setText(e.target.value)} />
        <button className="rounded-md bg-stone-900 px-3 text-sm text-white disabled:opacity-50" disabled={ask.isPending}>Ask</button>
      </form>
      {ask.isError && <p className="text-xs text-red-600">{ask.error.message}</p>}
    </div>
  )
}
