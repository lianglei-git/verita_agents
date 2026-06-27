import './DemoGoalImageView.less'

import { useEffect, useMemo, useState } from 'react'
import { ImageViewer } from '../../components/image-modal/ImageViewer'
import '../../components/image-modal/image-viewer.css'
import {
  DEFAULT_VISUAL_STYLE,
  EXAMPLE_SENTENCES,
  MODES,
  PARALLAX_LABELS,
  SPRITE_MAX,
  SPRITE_MIN,
  TEMPLATE_LABELS,
  TEXT_ROLE_LABELS,
  TEMPLATES,
  TILE_MAX,
  TILE_MIN,
  buildPayload,
  emptyPayload,
  parseInput,
} from './types'

function ModePicker({ value, onChange, disabled }) {
  return (
    <div className="template-picker" role="radiogroup" aria-label="生成模式">
      {MODES.map((opt) => (
        <button
          key={opt.id}
          type="button"
          role="radio"
          aria-checked={value === opt.id}
          className={`template-chip ${value === opt.id ? 'selected' : ''}`}
          onClick={() => onChange(opt.id)}
          disabled={disabled}
        >
          <span className="template-label">{opt.label}</span>
          <span className="template-hint">{opt.hint}</span>
        </button>
      ))}
    </div>
  )
}

function TemplatePicker({ value, onChange, disabled }) {
  return (
    <div className="template-picker" role="radiogroup" aria-label="动效模板">
      {TEMPLATES.map((opt) => (
        <button
          key={opt.id || 'auto'}
          type="button"
          role="radio"
          aria-checked={value === opt.id}
          className={`template-chip ${value === opt.id ? 'selected' : ''}`}
          onClick={() => onChange(opt.id)}
          disabled={disabled}
        >
          <span className="template-label">{opt.label}</span>
          <span className="template-hint">{opt.hint}</span>
        </button>
      ))}
    </div>
  )
}

function TileCard({ tile, onOpenImage }) {
  return (
    <article className="beat-card tile-card">
      <header>
        <span className="beat-id">第 {tile.index} 段</span>
        <p className="beat-narration">{tile.scene}</p>
      </header>
      <div className="beat-thumbs">
        <button type="button" onClick={() => onOpenImage(tile.preview)}>
          <img src={tile.preview} alt="" />
          <span>底图段</span>
        </button>
      </div>
    </article>
  )
}

function SpriteCard({ sprite, onOpenImage }) {
  return (
    <article className="beat-card sprite-card">
      <header>
        <span className="beat-id">精灵 {sprite.id}</span>
        <p className="beat-narration">{sprite.label}</p>
      </header>
      <div className="beat-thumbs">
        <button type="button" onClick={() => onOpenImage(sprite.preview || sprite.data_uri)}>
          <img src={sprite.preview || sprite.data_uri} alt="" />
          <span>抠图</span>
        </button>
      </div>
    </article>
  )
}

function downloadHtml(html, filename = 'result.html') {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function tilesDoneCount(meta) {
  const tiles = meta?.tiles
  if (Array.isArray(tiles) && tiles.length) return tiles.length
  const stages = meta?.stages || []
  return stages.filter((s) => typeof s === 'string' && /_done$/.test(s) && s.startsWith('tile_')).length
}

function spritesDoneCount(meta) {
  const stages = meta?.stages || []
  return stages.filter((s) => typeof s === 'string' && /_done$/.test(s) && s.startsWith('sprite_')).length
}

export default function DemoGoalImageView({
  mode,
  userInput,
  onInputChange,
  onRun,
  loading = false,
  result,
  reviewMode,
}) {
  const [form, setForm] = useState(() => parseInput(userInput))
  const [viewerOpen, setViewerOpen] = useState(false)
  const [viewerSrc, setViewerSrc] = useState('')

  useEffect(() => {
    setForm(parseInput(userInput))
  }, [userInput])

  const runResult = result?.result || null
  const html = runResult?.html || runResult?.output || ''
  const error = runResult?.error
  const meta = runResult?.meta || {}
  const isStripForm = form.mode !== 'single'
  const isStripResult =
    isStripForm &&
    (meta?.mode === 'continuous_strip' || Boolean(runResult?.strip_plan))
  const stripPlan = runResult?.strip_plan
  const tilePreviews = runResult?.tile_previews || []
  const spritePreviews = runResult?.sprite_previews || []
  const stripPreview = runResult?.assets_preview?.strip
  const plan = runResult?.scene_plan
  const apiReady = meta?.image_available !== false
  const tileCount = meta?.tile_count || stripPlan?.tile_count || tilePreviews.length
  const spriteCount = meta?.sprite_count || stripPlan?.sprite_count || spritePreviews.length
  const tilesGenerating = tilesDoneCount(meta)
  const spritesGenerating = spritesDoneCount(meta)

  useEffect(() => {
    if (!runResult) return
    const next = { ...form, sentence: runResult.sentence || form.sentence }
    if (runResult.strip_plan?.visual_style && !next.visual_style) {
      next.visual_style = runResult.strip_plan.visual_style
    }
    const json = JSON.stringify(next)
    setForm(next)
    onInputChange(json)
  }, [result])

  const sync = (next) => {
    setForm(next)
    onInputChange(JSON.stringify(next))
  }

  const generate = () => {
    if (!form.sentence.trim() || loading || !onRun) return
    const payload = buildPayload(form)
    const json = JSON.stringify(payload)
    setForm({ ...form, ...payload })
    onInputChange(json)
    onRun(json)
  }

  const openImage = (src) => {
    if (!src) return
    setViewerSrc(src)
    setViewerOpen(true)
  }

  const viewerImages = useMemo(() => {
    if (viewerSrc) return [{ src: viewerSrc, alt: '图层' }]
    return []
  }, [viewerSrc])

  const loadingHint = isStripForm
    ? `正在规划底图 ${TILE_MIN}–${TILE_MAX} 段 + 漫画精灵 ${SPRITE_MIN}–${SPRITE_MAX} 个 → 生成、抠图、拼接（较久，请耐心等待）…`
    : '正在解析意图 → 生成背景 / 主体图 → 抠图与文字层 → 渲染 HTML…'

  if (reviewMode) {
    return (
      <div className={`demo-goal-image-view mode-${mode} review`}>
        {html ? (
          <iframe className="parallax-preview-frame" title="长卷预览" srcDoc={html} sandbox="allow-scripts" />
        ) : (
          <p className="muted">本次运行未生成 HTML</p>
        )}
      </div>
    )
  }

  return (
    <div className={`demo-goal-image-view mode-${mode}`}>
      <header className="studio-header">
        <div>
          <p className="studio-eyebrow">Comic Parallax · 底图 + 精灵</p>
          <h2 className="studio-title">一句话，手绘长卷</h2>
          <p className="studio-lead">
            输入一句话故事，AI 生成无缝连续底图，并叠加 {SPRITE_MIN}–{SPRITE_MAX} 个小比例漫画精灵（不同视差速度），上滑穿越长卷。
          </p>
        </div>
        {!apiReady && (
          <p className="api-hint" role="status">
            未检测到图像 API 密钥，请配置 IMAGE_API_KEY 或 OPENAI_API_KEY
          </p>
        )}
      </header>

      <div className="studio-layout cinematic">
        <section className="prompt-studio" aria-label="故事输入">
          <label className="prompt-field">
            <span>一句话故事</span>
            <textarea
              rows={mode === 'standalone' ? 5 : 4}
              value={form.sentence}
              placeholder="例：雨后山间小路，远行者背着包一路向北"
              onChange={(e) => sync({ ...form, sentence: e.target.value })}
              disabled={loading}
            />
          </label>

          <div className="example-row">
            <span className="example-label">示例</span>
            <div className="example-chips">
              {EXAMPLE_SENTENCES.map((text) => (
                <button
                  key={text}
                  type="button"
                  className="example-chip"
                  onClick={() => sync({ ...form, sentence: text })}
                  disabled={loading}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>

          <label className="prompt-field style-field">
            <span>画风（可选，留空用手绘插画默认）</span>
            <input
              type="text"
              value={form.visual_style}
              placeholder={DEFAULT_VISUAL_STYLE}
              onChange={(e) => sync({ ...form, visual_style: e.target.value })}
              disabled={loading}
            />
          </label>

          <div className="size-block">
            <span className="field-label">模式</span>
            <ModePicker
              value={form.mode || 'series'}
              onChange={(m) => sync({ ...form, mode: m })}
              disabled={loading}
            />
          </div>

          {!isStripForm && (
            <div className="size-block">
              <span className="field-label">单幕动效</span>
              <TemplatePicker
                value={form.template || ''}
                onChange={(template) => sync({ ...form, template })}
                disabled={loading}
              />
            </div>
          )}

          <div className="studio-actions">
            <button
              type="button"
              className="generate-btn"
              onClick={generate}
              disabled={!form.sentence.trim() || loading || !apiReady}
            >
              {loading ? '生成中…' : isStripForm ? '生成底图 + 精灵长卷' : '生成单幕 HTML'}
            </button>
          </div>

          {loading && <p className="pipeline-hint">{loadingHint}</p>}

          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}

          {stripPlan && (
            <details className="plan-panel" open={!html}>
              <summary>
                长卷规划 · {stripPlan.title}
                {tileCount ? ` · ${tileCount} 段底图` : ''}
                {spriteCount ? ` · ${spriteCount} 精灵` : ''}
              </summary>
              <p className="plan-style">
                画风：{stripPlan.visual_style}
                <br />
                主角：{stripPlan.character_anchor}
              </p>
              <p className="plan-section-label">底图段</p>
              <ol className="beat-plan-list">
                {stripPlan.background_tiles?.map((t) => (
                  <li key={t.index}>
                    <strong>第 {t.index} 段</strong> {t.scene}
                    {t.seam_bottom ? (
                      <span className="text-meta"> · 底边衔接：{t.seam_bottom}</span>
                    ) : null}
                  </li>
                ))}
              </ol>
              {stripPlan.sprites?.length > 0 && (
                <>
                  <p className="plan-section-label">漫画精灵</p>
                  <ol className="beat-plan-list">
                    {stripPlan.sprites.map((s) => (
                      <li key={s.id}>
                        <strong>{s.label}</strong>
                        <span className="text-meta">
                          {' '}
                          · 锚定第 {s.anchor_tile} 段 · {PARALLAX_LABELS[s.parallax] || s.parallax}
                          {s.show_text ? (
                            <>
                              {' '}
                              · 「{s.text_content}」({TEXT_ROLE_LABELS[s.text_role] || s.text_role})
                            </>
                          ) : (
                            ' · 纯精灵无字'
                          )}
                        </span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </details>
          )}

          {plan && !stripPlan && (
            <details className="plan-panel" open={!html}>
              <summary>单幕规划</summary>
              <dl>
                {plan.visual_style && (
                  <div>
                    <dt>画风</dt>
                    <dd>{plan.visual_style}</dd>
                  </div>
                )}
                <div>
                  <dt>背景</dt>
                  <dd>{plan.background_prompt}</dd>
                </div>
                {plan.cinematic_template && (
                  <div>
                    <dt>动效</dt>
                    <dd>{TEMPLATE_LABELS[plan.cinematic_template] || plan.cinematic_template}</dd>
                  </div>
                )}
              </dl>
            </details>
          )}
        </section>

        <section className="preview-studio" aria-label="长卷预览">
          <div className="preview-meta">
            <span className="preview-label">{isStripResult ? '底图 + 精灵长卷' : '滚动预览'}</span>
            {meta?.parse_source && <span className="size-tag">解析：{meta.parse_source}</span>}
            {tileCount > 0 && <span className="model-tag">{tileCount} 段底图</span>}
            {spriteCount > 0 && <span className="model-tag">{spriteCount} 精灵</span>}
            {runResult?.assets_preview?.strip_height && (
              <span className="size-tag">
                {runResult.assets_preview.strip_width}×{runResult.assets_preview.strip_height}
              </span>
            )}
          </div>

          {stripPreview && (
            <button type="button" className="strip-thumb-btn" onClick={() => openImage(stripPreview)}>
              <img src={stripPreview} alt="拼接长卷预览" className="strip-thumb" />
              <span>查看完整长卷底图</span>
            </button>
          )}

          {(tilePreviews.length > 0 || spritePreviews.length > 0) && (
            <div className="beats-grid">
              {tilePreviews.map((tile) => (
                <TileCard key={`tile-${tile.index}`} tile={tile} onOpenImage={openImage} />
              ))}
              {spritePreviews.map((sprite) => (
                <SpriteCard key={`sprite-${sprite.id}`} sprite={sprite} onOpenImage={openImage} />
              ))}
            </div>
          )}

          <div className={`parallax-preview-wrap ${html ? 'has-html' : ''} ${loading ? 'is-loading' : ''}`}>
            {html ? (
              <iframe
                className="parallax-preview-frame"
                title="长卷滚动预览"
                srcDoc={html}
                sandbox="allow-scripts"
              />
            ) : (
              <div className="parallax-placeholder">
                <p>
                  {loading
                    ? tilesGenerating < tileCount
                      ? `正在生成第 ${tilesGenerating || '…'}/${tileCount || '…'} 段底图…`
                      : `正在生成精灵 ${spritesGenerating || '…'}/${spriteCount || '…'}（抠图中）…`
                    : '生成后在此上滑，底图连续推进，漫画精灵以不同速度掠过'}
                </p>
              </div>
            )}
          </div>

          {html && (
            <div className="export-actions">
              <button type="button" className="generate-btn" onClick={() => downloadHtml(html)}>
                下载 result.html
              </button>
              <button
                type="button"
                className="ghost-btn"
                onClick={() => navigator.clipboard?.writeText(html)}
              >
                复制 HTML
              </button>
            </div>
          )}
        </section>
      </div>

      {viewerOpen && viewerImages.length > 0 && (
        <ImageViewer images={viewerImages} initialIndex={0} onClose={() => setViewerOpen(false)} />
      )}
    </div>
  )
}
