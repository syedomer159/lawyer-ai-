import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

// The only way the UI talks to the backend. Types come from the backend's OpenAPI schema.
export const api = createClient<paths>({ baseUrl: '/' })

type Schemas = components['schemas']
export type Case = Schemas['Case']
export type CaseCreate = Schemas['CaseCreate']
export type Document = Schemas['Document']
export type PageDetail = Schemas['PageDetail']
export type SearchHit = Schemas['SearchHit']
// openapi-fetch widens JSON tuples to arrays in response types, so a bbox arrives typed as
// number[]. The backend contract (SourceRef / ChunkView) guarantees exactly [x0, y0, x1, y1].
export type BBox = number[]

function errorDetail(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
}

/** openapi-fetch returns {data, error}; React Query wants a value or a thrown error. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.error !== undefined || res.data === undefined) {
    throw new Error(errorDetail(res.error) ?? `Request failed (${res.response.status})`)
  }
  return res.data
}

/** Used as an <img src>, so it is a URL rather than a fetch. */
export function pageImageUrl(caseId: string, docId: string, page: number): string {
  return `/api/cases/${caseId}/documents/${docId}/pages/${page}/image`
}
