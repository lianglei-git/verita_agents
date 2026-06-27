export const TILE_MIN = 3
export const TILE_MAX = 8
export const SPRITE_MIN = 2
export const SPRITE_MAX = 5

export const DEFAULT_VISUAL_STYLE = '日系手绘插画，柔和粉彩，细线描边'

export const MODES = [
  { id: 'series', label: '连续长卷', hint: '底图+精灵' },
  { id: 'single', label: '单幕', hint: '快速' },
]

export const TEMPLATES = [
  { id: '', label: '自动', hint: 'scroll_follow' },
  { id: 'scroll_follow', label: '跟滚视差', hint: '微信长图' },
  { id: 'zoom_in', label: '推镜头', hint: 'zoom_in' },
  { id: 'parallax_horizontal', label: '横移', hint: 'slide' },
]

export const EXAMPLE_SENTENCES = [
  '雨后山间小路，远行者背着包一路向北',
  '小镇火车站，戴白帽的旅人寻找方向',
  '深夜书桌与台灯，专注画画的少年',
]

export const PARALLAX_LABELS = {
  scroll_follow: '跟滚',
  slow: '慢层',
  fast: '快层',
  fixed: '固定',
}

export const TEXT_ROLE_LABELS = {
  title: '标题',
  dialogue: '对白',
  narration: '旁白',
  sfx: '拟声',
  none: '无字',
}

export function emptyPayload() {
  return {
    sentence: '',
    mode: 'series',
    visual_style: '',
    template: '',
  }
}

export function parseInput(value) {
  if (!value?.trim()) return emptyPayload()
  try {
    const data = JSON.parse(value)
    if (typeof data === 'object' && data !== null) {
      return {
        ...emptyPayload(),
        sentence: String(data.sentence || data.prompt || '').trim(),
        mode: data.mode === 'single' ? 'single' : 'series',
        visual_style: String(data.visual_style || '').trim(),
        template: data.template || data.cinematic_template || '',
      }
    }
  } catch {
    /* plain text */
  }
  return { ...emptyPayload(), sentence: value.trim() }
}

export function buildPayload(form) {
  const payload = {
    sentence: form.sentence.trim(),
    mode: form.mode || 'series',
  }
  if (form.visual_style?.trim()) payload.visual_style = form.visual_style.trim()
  if (form.mode === 'single' && form.template) payload.template = form.template
  return payload
}

export const STAGE_LABELS = {
  parse_source: '意图解析',
  generate_background: '生成背景',
  generate_subject: '生成主体',
  render_text: '渲染文字',
  encode_assets: '编码素材',
  stitch_strip: '拼接长卷',
  encode_strip: '编码长卷',
  render_html: '渲染 HTML',
}

export const TEMPLATE_LABELS = {
  scroll_follow: '跟滚视差',
  zoom_in: '推镜头',
  parallax_horizontal: '横移',
}
