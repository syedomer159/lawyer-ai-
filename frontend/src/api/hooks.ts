import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type CaseCreate, type Document } from './client'

const POLL_MS = 1500

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: async () => unwrap(await api.GET('/api/health')) })
}

export function useCases() {
  return useQuery({ queryKey: ['cases'], queryFn: async () => unwrap(await api.GET('/api/cases')) })
}

export function useCase(caseId: string) {
  return useQuery({
    queryKey: ['case', caseId],
    queryFn: async () =>
      unwrap(await api.GET('/api/cases/{case_id}', { params: { path: { case_id: caseId } } })),
  })
}

export function useCreateCase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: CaseCreate) => unwrap(await api.POST('/api/cases', { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cases'] }),
  })
}

export function useDeleteCase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (caseId: string) => {
      const res = await api.DELETE('/api/cases/{case_id}', { params: { path: { case_id: caseId } } })
      if (!res.response.ok) throw new Error(`Delete failed (${res.response.status})`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cases'] }),
  })
}

const isBusy = (docs: Document[] | undefined) =>
  docs?.some((d) => d.status === 'queued' || d.status === 'processing') ?? false

export function useDocuments(caseId: string) {
  return useQuery({
    queryKey: ['documents', caseId],
    queryFn: async () =>
      unwrap(await api.GET('/api/cases/{case_id}/documents', { params: { path: { case_id: caseId } } })),
    refetchInterval: (query) => (isBusy(query.state.data) ? POLL_MS : false),
  })
}

export function useUpload(caseId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (files: File[]) =>
      unwrap(
        await api.POST('/api/cases/{case_id}/documents', {
          params: { path: { case_id: caseId } },
          body: { files },
          bodySerializer: (body) => {
            const form = new FormData()
            body.files.forEach((f) => form.append('files', f))
            return form
          },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', caseId] }),
  })
}

export function usePage(caseId: string, docId: string, page: number) {
  return useQuery({
    queryKey: ['page', caseId, docId, page],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/cases/{case_id}/documents/{doc_id}/pages/{page}', {
          params: { path: { case_id: caseId, doc_id: docId, page } },
        }),
      ),
  })
}

export function useSearch(caseId: string, q: string) {
  return useQuery({
    queryKey: ['search', caseId, q],
    enabled: q.trim().length > 0,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/cases/{case_id}/search', {
          params: { path: { case_id: caseId }, query: { q } },
        }),
      ),
  })
}

export function useUsage(caseId: string) {
  return useQuery({
    queryKey: ['usage', caseId],
    queryFn: async () =>
      unwrap(await api.GET('/api/cases/{case_id}/usage', { params: { path: { case_id: caseId } } })),
  })
}

// Analysis types as the UI receives them (derived from the fetched data, see BBox in client.ts).
export type AnalysisData = NonNullable<ReturnType<typeof useAnalysis>['data']>
export type ConflictData = AnalysisData['conflicts'][number]
export type ClaimData = ConflictData['claims'][number]
export type CitationData = ClaimData['citation']
export type ElementData = AnalysisData['elements'][number]
export type IssueData = AnalysisData['issues'][number]

export function useAnalysis(caseId: string) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: ['analysis', caseId],
    queryFn: async () => {
      const data = unwrap(
        await api.GET('/api/cases/{case_id}/analysis', { params: { path: { case_id: caseId } } }),
      )
      if (data.job?.status !== 'running') qc.invalidateQueries({ queryKey: ['usage', caseId] })
      return data
    },
    refetchInterval: (query) => (query.state.data?.job?.status === 'running' ? POLL_MS : false),
  })
}

export function useStartAnalysis(caseId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/cases/{case_id}/analysis', { params: { path: { case_id: caseId } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['analysis', caseId] }),
  })
}

export function useSetConflictStatus(caseId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, status }: { id: number; status: 'open' | 'dismissed' }) => {
      const res = await api.PATCH('/api/cases/{case_id}/conflicts/{conflict_id}', {
        params: { path: { case_id: caseId, conflict_id: id } },
        body: { status },
      })
      if (!res.response.ok) throw new Error(`Update failed (${res.response.status})`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['analysis', caseId] }),
  })
}

// --- mock trial ---------------------------------------------------------------------------

export type TrialSessionData = NonNullable<ReturnType<typeof useTrialSession>['data']>
export type TrialWitnessInput = { name: string; role: TrialSessionData['witnesses'][number]['role']; demeanour: 'cooperative' | 'nervous' | 'hostile' }

export function useTrialWitnesses(caseId: string) {
  return useQuery({
    queryKey: ['trial-witnesses', caseId],
    queryFn: async () =>
      unwrap(await api.GET('/api/cases/{case_id}/trial/witnesses', { params: { path: { case_id: caseId } } })),
  })
}

export function useTrialSessions(caseId: string) {
  return useQuery({
    queryKey: ['trial-sessions', caseId],
    queryFn: async () =>
      unwrap(await api.GET('/api/cases/{case_id}/trial/sessions', { params: { path: { case_id: caseId } } })),
  })
}

export function useTrialSession(caseId: string, sessionId: string | null) {
  return useQuery({
    queryKey: ['trial-session', caseId, sessionId],
    enabled: sessionId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/cases/{case_id}/trial/sessions/{session_id}', {
          params: { path: { case_id: caseId, session_id: sessionId ?? '' } },
        }),
      ),
  })
}

/** Every trial action returns the updated session; put it straight into the cache. */
function useTrialAction<Vars>(caseId: string, run: (vars: Vars) => Promise<TrialSessionData>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSuccess: (session) => {
      qc.setQueryData(['trial-session', caseId, session.id], session)
      qc.invalidateQueries({ queryKey: ['trial-sessions', caseId] })
      qc.invalidateQueries({ queryKey: ['usage', caseId] })
    },
  })
}

export function useStartTrial(caseId: string) {
  return useTrialAction(caseId, async (witnesses: TrialWitnessInput[]) =>
    unwrap(
      await api.POST('/api/cases/{case_id}/trial/sessions', {
        params: { path: { case_id: caseId } },
        body: { witnesses },
      }),
    ),
  )
}

export function useTrialTurn(caseId: string, sessionId: string) {
  return useTrialAction(caseId, async (body: { kind: 'question' | 'argument' | 'objection'; text: string }) =>
    unwrap(
      await api.POST('/api/cases/{case_id}/trial/sessions/{session_id}/turns', {
        params: { path: { case_id: caseId, session_id: sessionId } },
        body,
      }),
    ),
  )
}

export function useTrialAdvance(caseId: string, sessionId: string) {
  return useTrialAction(caseId, async () =>
    unwrap(
      await api.POST('/api/cases/{case_id}/trial/sessions/{session_id}/advance', {
        params: { path: { case_id: caseId, session_id: sessionId } },
      }),
    ),
  )
}

export function useTrialDebrief(caseId: string, sessionId: string) {
  return useTrialAction(caseId, async () =>
    unwrap(
      await api.POST('/api/cases/{case_id}/trial/sessions/{session_id}/debrief', {
        params: { path: { case_id: caseId, session_id: sessionId } },
      }),
    ),
  )
}

// --- case assistant -----------------------------------------------------------------------

export function useAssistant(caseId: string) {
  return useQuery({
    queryKey: ['assistant', caseId],
    queryFn: async () =>
      unwrap(await api.GET('/api/cases/{case_id}/assistant', { params: { path: { case_id: caseId } } })),
  })
}

export function useAsk(caseId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(await api.POST('/api/cases/{case_id}/assistant', { params: { path: { case_id: caseId } }, body: { text } })),
    onSuccess: (messages) => {
      qc.setQueryData(['assistant', caseId], messages)
      qc.invalidateQueries({ queryKey: ['usage', caseId] })
    },
  })
}
