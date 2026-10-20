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
