import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { useCases, useCreateCase, useDeleteCase } from '../api/hooks'

export default function CasesPage() {
  const cases = useCases()
  const remove = useDeleteCase()

  return (
    <main className="mx-auto max-w-4xl space-y-8 p-6">
      <NewCaseForm />
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">Cases</h2>
        {cases.isError && <p className="text-sm text-red-600">{cases.error.message}</p>}
        {cases.data?.length === 0 && <p className="text-sm text-stone-500">No cases yet.</p>}
        <ul className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
          {cases.data?.map((c) => (
            <li key={c.id} className="flex items-center justify-between px-4 py-3">
              <Link to={`/cases/${c.id}`} className="min-w-0">
                <div className="font-medium hover:underline">{c.title}</div>
                <div className="text-xs text-stone-500">
                  Client {c.client} · {c.user_side} · {c.charges.join(', ') || 'no charges listed'}
                  {c.local_only && ' · local models only'}
                </div>
              </Link>
              <button
                className="text-xs text-stone-400 hover:text-red-600"
                onClick={() => confirm(`Delete "${c.title}" and all its files?`) && remove.mutate(c.id)}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  )
}

function NewCaseForm() {
  const create = useCreateCase()
  const [title, setTitle] = useState('')
  const [client, setClient] = useState('')
  const [charges, setCharges] = useState('')
  const [userSide, setUserSide] = useState<'defence' | 'prosecution'>('defence')
  const [localOnly, setLocalOnly] = useState(false)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      {
        title,
        client,
        user_side: userSide,
        local_only: localOnly,
        charges: charges.split(',').map((s) => s.trim()).filter(Boolean),
      },
      { onSuccess: () => [setTitle, setClient, setCharges].forEach((set) => set('')) },
    )
  }

  const input = 'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm'
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-stone-200 bg-white p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">New case</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <input className={input} placeholder="Title, e.g. State v. Arjun Verma" value={title}
          onChange={(e) => setTitle(e.target.value)} required />
        <input className={input} placeholder="Client" value={client}
          onChange={(e) => setClient(e.target.value)} required />
        <input className={input} placeholder="Charges, comma separated (e.g. BNS 304(2))" value={charges}
          onChange={(e) => setCharges(e.target.value)} />
        <select className={input} value={userSide}
          onChange={(e) => setUserSide(e.target.value === 'prosecution' ? 'prosecution' : 'defence')}>
          <option value="defence">I am defence counsel</option>
          <option value="prosecution">I am the prosecutor</option>
        </select>
      </div>
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-stone-600">
          <input type="checkbox" checked={localOnly} onChange={(e) => setLocalOnly(e.target.checked)} />
          Confidential: use local models only (nothing leaves this machine)
        </label>
        <button className="rounded-md bg-stone-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          disabled={create.isPending}>
          Create case
        </button>
      </div>
      {create.isError && <p className="text-sm text-red-600">{create.error.message}</p>}
    </form>
  )
}
