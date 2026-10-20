import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'

export default function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/health')
      if (error) throw new Error('Backend health check failed')
      return data
    },
  })

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">Lawyer AI — case prep</h1>
      <p className="mt-2 text-sm text-gray-600">
        Backend:{' '}
        {health.isPending ? 'checking…' : health.isError ? 'unreachable' : `${health.data.status} (profile: ${health.data.model_profile})`}
      </p>
    </main>
  )
}
