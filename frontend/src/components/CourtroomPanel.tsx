import { useState } from 'react'
import {
  useStartTrial,
  useTrialAdvance,
  useTrialDebrief,
  useTrialSession,
  useTrialSessions,
  useTrialTurn,
  useTrialWitnesses,
  type TrialSessionData,
  type TrialWitnessInput,
} from '../api/hooks'

const PHASES = ['opening', 'chief', 'cross', 'final', 'judgment', 'closed'] as const
const PHASE_LABEL: Record<(typeof PHASES)[number], string> = {
  opening: 'Opening', chief: 'Exam-in-chief', cross: 'Cross', final: 'Final arguments', judgment: 'Observations', closed: 'Closed',
}
const GROUNDS = ['Leading question in examination-in-chief', 'Irrelevant', 'Assumes facts not in evidence', 'Calls for speculation', 'Argumentative']
const DEMEANOURS = ['cooperative', 'nervous', 'hostile'] as const

export default function CourtroomPanel({ caseId }: { caseId: string }) {
  const sessions = useTrialSessions(caseId)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const active = sessionId ?? sessions.data?.[0]?.id ?? null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {sessions.data?.map((s, i) => (
          <button key={s.id} onClick={() => setSessionId(s.id)}
            className={`rounded border px-2 py-1 ${s.id === active ? 'border-stone-900' : 'border-stone-300 text-stone-500'}`}>
            Trial {sessions.data.length - i} · {s.witnesses.join(', ')} · {s.phase}
          </button>
        ))}
        {active && <button className="rounded border border-dashed border-stone-400 px-2 py-1" onClick={() => setSessionId('new')}>+ New trial</button>}
      </div>
      {active && active !== 'new' ? (
        <Session caseId={caseId} sessionId={active} />
      ) : (
        <Setup caseId={caseId} onStarted={setSessionId} />
      )}
    </div>
  )
}

function Setup({ caseId, onStarted }: { caseId: string; onStarted: (id: string) => void }) {
  const witnesses = useTrialWitnesses(caseId)
  const start = useStartTrial(caseId)
  const [picked, setPicked] = useState<Record<string, TrialWitnessInput>>({})

  if (witnesses.data?.length === 0) {
    return <p className="text-sm text-stone-500">Run the case analysis first: it finds the witnesses who can be called.</p>
  }
  return (
    <div className="space-y-3 rounded-lg border border-stone-200 bg-white p-4">
      <h3 className="text-sm font-semibold">Call witnesses (in order)</h3>
      <ul className="space-y-1">
        {witnesses.data?.map((p) => {
          const chosen = picked[p.name]
          return (
            <li key={p.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!chosen} onChange={(e) => {
                const next = { ...picked }
                if (e.target.checked) next[p.name] = { name: p.name, role: p.role, demeanour: 'cooperative' }
                else delete next[p.name]
                setPicked(next)
              }} />
              <span className="flex-1">{p.name} <span className="text-xs text-stone-400">({p.role})</span></span>
              {chosen && (
                <select className="rounded border border-stone-300 text-xs" value={chosen.demeanour}
                  onChange={(e) => setPicked({ ...picked, [p.name]: { ...chosen, demeanour: DEMEANOURS.find((d) => d === e.target.value) ?? 'cooperative' } })}>
                  {DEMEANOURS.map((d) => <option key={d}>{d}</option>)}
                </select>
              )}
            </li>
          )
        })}
      </ul>
      <button className="rounded-md bg-stone-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        disabled={Object.keys(picked).length === 0 || start.isPending}
        onClick={() => start.mutate(Object.values(picked), { onSuccess: (s) => onStarted(s.id) })}>
        {start.isPending ? 'Court is assembling…' : 'Start mock trial'}
      </button>
      {start.isError && <p className="text-xs text-red-600">{start.error.message}</p>}
    </div>
  )
}

function Session({ caseId, sessionId }: { caseId: string; sessionId: string }) {
  const session = useTrialSession(caseId, sessionId)
  const s = session.data
  if (session.isError) return <p className="text-sm text-red-600">{session.error.message}</p>
  if (!s) return <p className="text-sm text-stone-500">Loading…</p>
  return (
    <div className="space-y-3">
      <ol className="flex flex-wrap gap-1 text-[11px]">
        {PHASES.map((p) => (
          <li key={p} className={`rounded px-2 py-0.5 ${p === s.phase ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-500'}`}>
            {PHASE_LABEL[p]}
          </li>
        ))}
      </ol>
      <Transcript session={s} />
      <p className="text-xs text-stone-600">{s.hint}</p>
      {s.awaiting_user && <Controls caseId={caseId} session={s} />}
      <DebriefView caseId={caseId} session={s} />
    </div>
  )
}

function Transcript({ session }: { session: TrialSessionData }) {
  const you = session.user_side === 'defence' ? 'Defence Counsel' : 'Public Prosecutor'
  return (
    <ol className="max-h-[32rem] space-y-2 overflow-y-auto rounded-lg border border-stone-200 bg-white p-3">
      {session.turns.map((t) => (
        <li key={t.id} className={`text-sm ${t.struck ? 'text-stone-400 line-through' : ''}`}>
          <span className={`mr-1 font-semibold ${
            t.speaker === 'judge' ? 'text-indigo-800' : t.speaker === 'user' ? 'text-emerald-800' : t.speaker === 'counsel' ? 'text-red-800' : 'text-stone-800'
          }`}>
            {t.speaker === 'user' ? `${you} (you)` : t.speaker_name}:
          </span>
          {t.text}
        </li>
      ))}
    </ol>
  )
}

function Controls({ caseId, session }: { caseId: string; session: TrialSessionData }) {
  const turn = useTrialTurn(caseId, session.id)
  const advance = useTrialAdvance(caseId, session.id)
  const [text, setText] = useState('')
  const [ground, setGround] = useState(GROUNDS[0])
  const busy = turn.isPending || advance.isPending
  const arguing = session.phase === 'final'
  const argued = session.turns.some((t) => t.phase === 'final' && t.speaker === 'user')
  const lastCounsel = [...session.turns].reverse().find((t) => t.speaker === 'counsel' && !t.struck)

  return (
    <div className="space-y-2 rounded-lg border border-stone-200 bg-white p-3">
      {!(arguing && argued) && (
        <form className="flex gap-2" onSubmit={(e) => {
          e.preventDefault()
          if (text.trim()) turn.mutate({ kind: arguing ? 'argument' : 'question', text }, { onSuccess: () => setText('') })
        }}>
          <textarea className="min-h-16 flex-1 rounded-md border border-stone-300 px-2 py-1 text-sm" value={text}
            placeholder={arguing ? 'Your final argument to the court…' : 'Your question to the witness…'}
            onChange={(e) => setText(e.target.value)} />
          <button className="self-end rounded-md bg-stone-900 px-3 py-1.5 text-sm text-white disabled:opacity-50" disabled={busy}>
            {arguing ? 'Argue' : 'Ask'}
          </button>
        </form>
      )}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button className="rounded-md border border-stone-300 px-2 py-1 disabled:opacity-50" disabled={busy || (arguing && !argued)}
          onClick={() => advance.mutate()}>
          {arguing ? 'Proceed to observations' : 'No further questions'}
        </button>
        {lastCounsel && (
          <>
            <select className="rounded border border-stone-300" value={ground} onChange={(e) => setGround(e.target.value)}>
              {GROUNDS.map((g) => <option key={g}>{g}</option>)}
            </select>
            <button className="rounded-md border border-red-300 px-2 py-1 text-red-700 disabled:opacity-50" disabled={busy}
              onClick={() => turn.mutate({ kind: 'objection', text: ground })}>
              Object to opposing counsel
            </button>
          </>
        )}
        {busy && <span className="text-stone-500">The court is responding…</span>}
      </div>
      {(turn.isError || advance.isError) && <p className="text-xs text-red-600">{(turn.error ?? advance.error)?.message}</p>}
    </div>
  )
}

function DebriefView({ caseId, session }: { caseId: string; session: TrialSessionData }) {
  const run = useTrialDebrief(caseId, session.id)
  const d = session.debrief
  const participated = session.turns.some((t) => t.speaker === 'user')
  if (!d) {
    return participated ? (
      <button className="rounded-md border border-stone-300 px-3 py-1.5 text-sm disabled:opacity-50" disabled={run.isPending} onClick={() => run.mutate()}>
        {run.isPending ? 'Coach is reviewing…' : 'Debrief my performance'}
      </button>
    ) : null
  }
  return (
    <section className="space-y-2 rounded-lg border border-emerald-200 bg-white p-4 text-sm">
      <h3 className="font-semibold">Debrief · {d.score}/10</h3>
      <p>{d.summary}</p>
      <List title="Strengths" items={d.strengths} />
      <List title="Missed" items={d.missed} />
      <List title="Better questions" items={d.better_questions.map((q) => `${q.witness}: ${q.question}`)} />
    </section>
  )
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">{title}</div>
      <ul className="list-disc pl-5">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  )
}
