import createClient from 'openapi-fetch'
import type { paths } from './schema'

// The only way the UI talks to the backend. Types come from the backend's OpenAPI schema.
export const api = createClient<paths>({ baseUrl: '/' })
