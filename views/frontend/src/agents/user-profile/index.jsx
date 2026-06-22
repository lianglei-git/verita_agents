import './UserProfileView.less'

import { useEffect, useMemo, useState } from 'react'

const EMPTY = {
  career: '',
  level: '',
  goal: '',
  preference: '',
  fear: '',
}

function parseInput(value) {
  if (!value?.trim()) return { ...EMPTY }
  try {
    const data = JSON.parse(value)
    return { ...EMPTY, ...data }
  } catch {
    return { ...EMPTY, goal: value }
  }
}

export default function UserProfileView({
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

  const profile = useMemo(() => {
    if (!result?.result) return null
    const r = result.result
    return r.profile || null
  }, [result])

  const update = (key, val) => {
    const next = { ...form, [key]: val }
    setForm(next)
    onInputChange(JSON.stringify(next, null, 0))
  }

  if (reviewMode) {
    return (
      <div className={`user-profile-view mode-${mode} review`}>
        {profile ? (
          <div className="profile-card">
            <h3>{profile.persona_title}</h3>
            <p>{profile.summary}</p>
          </div>
        ) : (
          <p className="muted">无画像输出</p>
        )}
      </div>
    )
  }

  return (
    <div className={`user-profile-view mode-${mode}`}>
      <div className="profile-form">
        <label>
          <span>职业 / 现状</span>
          <input
            value={form.career}
            placeholder="例：前端工程师，工作 3 年"
            onChange={(e) => update('career', e.target.value)}
          />
        </label>
        <label>
          <span>英语水平</span>
          <input
            value={form.level}
            placeholder="例：B1，能读文档，口语弱"
            onChange={(e) => update('level', e.target.value)}
          />
        </label>
        <label>
          <span>目标</span>
          <input
            value={form.goal}
            placeholder="例：6 个月内通过海外技术面试"
            onChange={(e) => update('goal', e.target.value)}
          />
        </label>
        <label>
          <span>学习偏好</span>
          <input
            value={form.preference}
            placeholder="例：场景化、短课时、需要即时反馈"
            onChange={(e) => update('preference', e.target.value)}
          />
        </label>
        <label>
          <span>最害怕的场景</span>
          <input
            value={form.fear}
            placeholder="例：视频会议里听不懂对方在问什么"
            onChange={(e) => update('fear', e.target.value)}
          />
        </label>
      </div>

      {mode === 'standalone' && profile && (
        <div className="profile-card output">
          <span className="card-label">生成画像</span>
          <h3>{profile.persona_title}</h3>
          <p className="summary">{profile.summary}</p>
          <ul>
            {profile.gaps?.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
