import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import './App.css'
import App from './App.tsx'
import ProblemsListPage from './pages/ProblemsListPage.tsx'
import ProblemDetailPage from './pages/ProblemDetailPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/problems" element={<ProblemsListPage />} />
        <Route path="/problems/:id" element={<ProblemDetailPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
