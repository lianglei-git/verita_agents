import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { fetchAgents } from '../api/client'
import AppShell from '../components/AppShell'
import '../components/AppShell.less'
import './AgentList.less'

export default function AgentList() {
  const [agents, setAgents] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    fetchAgents()
      .then((data) => setAgents(data.agents || []))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <AppShell
      eyebrow="Verita · Workbench"
      title="独立工作台"
      description="单独开发与调试某个 Agent，不依赖整条流水线。"
    >
      {error && <div className="error-banner">{error}</div>}

      <section className="agent-list-page">
        <ul>
          {agents.map((agent) => (
            <li key={agent.id}>
              <Link to={`/agent/${agent.id}`} className="agent-card">
                <div className="card-top">
                  <span className="agent-id">{agent.id}</span>
                  <span className={`view-tag ${agent.view?.type || 'default'}`}>
                    {agent.view?.type === 'custom' ? '自定义 UI' : '通用 UI'}
                  </span>
                </div>
                <h2>{agent.name}</h2>
                <p>{agent.description}</p>
                {agent.phase && <span className="phase">{agent.phase}</span>}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </AppShell>
  )
}
