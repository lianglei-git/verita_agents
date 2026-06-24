import './RoutePlannerView.less'

import { useEffect, useState } from 'react'

const ROUTE_OPTIONS = [
  {
    id: 'global-career-interview',
    name: '海外面试线',
    tagline: '前端 → 海外面试 → 项目表达 → 远程协作',
  },
  {
    id: 'remote-work',
    name: '远程工作线',
    tagline: '沟通 → 异步协作 → 跨时区会议',
  },
  {
    id: 'study-abroad',
    name: '留学考试线',
    tagline: '学术英语 → 考试技巧 → 申请沟通',
  },
]

function parseInput(value) {
  if (!value?.trim()) return { goal: '', route_id: '' }
  try {
    return { goal: '', route_id: '', ...JSON.parse(value) }
  } catch {
    return { goal: value, route_id: '' }
  }
}

export default function RoutePlannerView({
  mode,
  userInput,
  onInputChange,
  result,
  reviewMode,
}) {
  const [form, setForm] = useState(() => parseInput(userInput))

  useEffect(() => {
    setForm(parseInput(userInput))
  }, [userInput])

  const plan = result?.result?.plan
  const alternatives = result?.result?.alternatives || []

  const sync = (next) => {
    setForm(next)
    onInputChange(JSON.stringify(next))
  }

  const selectRoute = (routeId) => {
    sync({ ...form, route_id: routeId })
  }

  if (reviewMode && plan) {
    return (
      <div className={`route-planner-view mode-${mode} review`}>
        <PlanCard plan={plan} />
      </div>
    )
  }

  return (
    <div className={`route-planner-view mode-${mode}`}>
      <p className="intro">
        选择一条成长路线，或留空由系统根据上游画像 / 目标自动推荐。
      </p>

      <label className="goal-field">
        <span>学习目标（无上游画像时填写）</span>
        <input
          value={form.goal || ''}
          placeholder="例：海外技术面试、远程工作"
          onChange={(e) => sync({ ...form, goal: e.target.value })}
        />
      </label>

      <div className="route-cards">
        {ROUTE_OPTIONS.map((route) => (
          <button
            key={route.id}
            type="button"
            className={`route-card ${form.route_id === route.id ? 'selected' : ''}`}
            onClick={() => selectRoute(route.id)}
          >
            <span className="route-name">{route.name}</span>
            <span className="route-tagline">{route.tagline}</span>
          </button>
        ))}
        <button
          type="button"
          className={`route-card auto ${!form.route_id ? 'selected' : ''}`}
          onClick={() => selectRoute('')}
        >
          <span className="route-name">自动推荐</span>
          <span className="route-tagline">根据目标关键词匹配最佳路线</span>
        </button>
      </div>

      {plan && (
        <div className="result-section">
          <h3>推荐结果</h3>
          <PlanCard plan={plan} />
          {alternatives.length > 0 && (
            <div className="alternatives">
              <span className="alt-label">其他路线</span>
              <ul>
                {alternatives.map((alt) => (
                  <li key={alt.id}>{alt.name} — {alt.tagline}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PlanCard({ plan }) {
  if (!plan) return null
  return (
    <div className="plan-card">
      <header>
        <h4>{plan.route_name}</h4>
        <span className="track">{plan.primary_track}</span>
      </header>
      <p className="tagline">{plan.tagline}</p>
      <p className="rationale">{plan.rationale}</p>
      <ol className="stages">
        {plan.stages?.map((stage, i) => (
          <li key={stage.id}>
            <span className="stage-num">{i + 1}</span>
            <div>
              <strong>{stage.title}</strong>
              <span>{stage.focus}</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
