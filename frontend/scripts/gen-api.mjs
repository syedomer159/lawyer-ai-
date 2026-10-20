// Generate src/api/schema.d.ts from the backend's OpenAPI schema (run via `npm run gen:api`).
// Uploaded files are typed as Blob instead of string so FormData uploads need no casts.
import { readFileSync, writeFileSync } from 'node:fs'
import openapiTS, { astToString } from 'openapi-typescript'
import ts from 'typescript'

const BLOB = ts.factory.createTypeReferenceNode(ts.factory.createIdentifier('Blob'))
const schema = JSON.parse(readFileSync('openapi.json', 'utf8'))
const ast = await openapiTS(schema, {
  transform(node) {
    if (node.contentMediaType === 'application/octet-stream') return BLOB
  },
})
writeFileSync('src/api/schema.d.ts', astToString(ast))
console.log('wrote src/api/schema.d.ts')
