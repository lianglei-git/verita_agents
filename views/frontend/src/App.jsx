import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Console from './pages/Console'
import AgentList from './pages/AgentList'
import AgentWorkbench from './pages/AgentWorkbench'
import './App.less'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Console />} />
        <Route path="/agents" element={<AgentList />} />
        <Route path="/agent/:id" element={<AgentWorkbench />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
