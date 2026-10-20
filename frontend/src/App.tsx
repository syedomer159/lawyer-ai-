import { BrowserRouter, Link, Route, Routes } from 'react-router'
import { useHealth } from './api/hooks'
import CaseWorkspace from './pages/CaseWorkspace'
import CasesPage from './pages/CasesPage'

function Header() {
  const health = useHealth()
  const status = health.isPending
    ? 'checking backend…'
    : health.isError
      ? 'backend unreachable'
      : `models: ${health.data.model_profile}`
  return (
    <header className="flex items-center justify-between border-b border-stone-200 bg-white px-6 py-3">
      <Link to="/" className="font-semibold tracking-tight text-stone-900">
        Lawyer AI <span className="font-normal text-stone-500">· case prep</span>
      </Link>
      <span className={`text-xs ${health.isError ? 'text-red-600' : 'text-stone-500'}`}>{status}</span>
    </header>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-stone-50 text-stone-900">
        <Header />
        <Routes>
          <Route path="/" element={<CasesPage />} />
          <Route path="/cases/:caseId" element={<CaseWorkspace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
