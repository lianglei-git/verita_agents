import { lazy, Suspense, useEffect, useState } from 'react'
import GenericAgentView from './GenericAgentView'
import { resolveAgentView } from './registry'
import './AgentViewResolver.less'

function ViewFallback() {
  return <div className="agent-view-loading">加载视图…</div>
}

export default function AgentViewResolver({
  agent,
  mode = 'embedded',
  userInput,
  onInputChange,
  onRun,
  loading = false,
  result,
  reviewMode = false,
  sessionKey,
}) {
  const viewType = agent?.view?.type || 'default'
  const [CustomView, setCustomView] = useState(null)

  useEffect(() => {
    if (viewType !== 'custom' || !agent?.id) {
      setCustomView(null)
      return undefined
    }

    let cancelled = false
    const loader = resolveAgentView(agent.id)
    if (!loader) {
      setCustomView(null)
      return undefined
    }

    loader().then((mod) => {
      if (!cancelled) setCustomView(() => mod.default)
    })

    return () => {
      cancelled = true
    }
  }, [agent?.id, viewType])

  if (!agent) return null

  const ViewComponent = viewType === 'custom' && CustomView ? CustomView : GenericAgentView

  return (
    <div className={`agent-view-resolver mode-${mode}`}>
      <Suspense fallback={<ViewFallback />}>
        <ViewComponent
          key={sessionKey ?? 'default'}
          agent={agent}
          mode={mode}
          userInput={userInput}
          onInputChange={onInputChange}
          onRun={onRun}
          loading={loading}
          result={result}
          reviewMode={reviewMode}
          schema={agent.schema}
        />
      </Suspense>
    </div>
  )
}
