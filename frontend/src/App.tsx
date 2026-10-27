import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { About } from './pages/About'
import { AgentTrace } from './pages/AgentTrace'
import { Dashboard } from './pages/Dashboard'
import { TestCasesPage } from './pages/TestCasesPage'
import { ValidationPage } from './pages/ValidationPage'
import { Workbench } from './pages/Workbench'
import { SessionProvider } from './store/SessionContext'

export default function App() {
  return (
    <SessionProvider>
      <HashRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/workbench" element={<Workbench />} />
            <Route path="/trace" element={<AgentTrace />} />
            <Route path="/report" element={<ValidationPage />} />
            <Route path="/tests" element={<TestCasesPage />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </HashRouter>
    </SessionProvider>
  )
}
