/**
 * GoalBridge 前端控制台调试（前缀 [GoalBridge]）
 * @module goal-bridge/debug
 */

const PREFIX = '[GoalBridge]'
const ENABLED = import.meta.env?.VITE_GOALBRIDGE_DEBUG !== '0'

/**
 * @param {string} phase
 * @param {Record<string, unknown>} [fields]
 */
export function gbLog(phase, fields = {}) {
  if (!ENABLED) return
  const label = `${PREFIX} ${phase}`
  if (typeof console.groupCollapsed === 'function') {
    console.groupCollapsed(label)
    Object.entries(fields).forEach(([key, val]) => {
      if (val !== undefined && val !== null) console.log(key, val)
    })
    console.groupEnd()
  } else {
    console.log(label, fields)
  }
}

/**
 * @param {string} phase
 * @param {unknown} err
 */
export function gbError(phase, err) {
  console.error(`${PREFIX} ${phase}`, err)
}
