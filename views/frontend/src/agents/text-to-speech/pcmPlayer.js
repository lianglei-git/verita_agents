/**
 * Queue PCM / WAV chunks on one continuous timeline.
 * Later fragments wait until earlier ones finish (no cut-off).
 */
export function createPcmPlayer(sampleRate = 24000) {
  let ctx = null
  let nextTime = 0
  let sentenceSamples = 0
  let decodeChain = Promise.resolve()
  const highlightTimers = []

  function ensureCtx() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext
      ctx = new AC({ sampleRate })
    }
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    return ctx
  }

  function scheduleBuffer(buffer) {
    const audioCtx = ensureCtx()
    const source = audioCtx.createBufferSource()
    source.buffer = buffer
    source.connect(audioCtx.destination)
    const startAt = Math.max(audioCtx.currentTime, nextTime)
    source.start(startAt)
    nextTime = startAt + buffer.duration
    sentenceSamples += buffer.length
    return startAt
  }

  function enqueueBytes(bytes) {
    const isRiff =
      bytes.length >= 12 &&
      bytes[0] === 0x52 &&
      bytes[1] === 0x49 &&
      bytes[2] === 0x46 &&
      bytes[3] === 0x46

    if (isRiff) {
      const copy = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
      decodeChain = decodeChain.then(
        () =>
          new Promise((resolve) => {
            ensureCtx().decodeAudioData(
              copy,
              (buffer) => {
                scheduleBuffer(buffer)
                resolve()
              },
              () => resolve(),
            )
          }),
      )
      return decodeChain
    }

    const sampleCount = Math.floor(bytes.length / 2)
    if (sampleCount <= 0) return Promise.resolve()
    const audioCtx = ensureCtx()
    const buffer = audioCtx.createBuffer(1, sampleCount, sampleRate)
    const channel = buffer.getChannelData(0)
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    for (let i = 0; i < sampleCount; i += 1) {
      channel[i] = view.getInt16(i * 2, true) / 32768
    }
    scheduleBuffer(buffer)
    return Promise.resolve()
  }

  function enqueueBase64Pcm(b64) {
    if (!b64) return Promise.resolve()
    const binary = atob(b64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
    return enqueueBytes(bytes)
  }

  /**
   * Mark a new sentence boundary on the timeline (after any pending WAV decodes).
   * onPlayStart fires when this sentence's audio actually begins (after prior fragments).
   */
  function beginSentence(index, onPlayStart) {
    decodeChain = decodeChain.then(() => {
      sentenceSamples = 0
      const audioCtx = ensureCtx()
      const startAt = Math.max(audioCtx.currentTime, nextTime)
      const delayMs = Math.max(0, (startAt - audioCtx.currentTime) * 1000)
      const timer = setTimeout(() => {
        onPlayStart?.(index)
      }, delayMs)
      highlightTimers.push(timer)
    })
    return decodeChain
  }

  function endSentenceDurationMs() {
    if (sentenceSamples <= 0) return 0
    return Math.round((sentenceSamples / sampleRate) * 1000)
  }

  /** Snapshot duration on the decode queue before the next beginSentence resets counters. */
  function captureSentenceDurationMs() {
    let captured = 0
    const p = decodeChain.then(() => {
      captured = endSentenceDurationMs()
    })
    decodeChain = p
    return p.then(() => captured)
  }

  function queuedUntilMs() {
    if (!ctx) return 0
    return Math.max(0, Math.round((nextTime - ctx.currentTime) * 1000))
  }

  async function stop() {
    for (const t of highlightTimers) clearTimeout(t)
    highlightTimers.length = 0
    decodeChain = Promise.resolve()
    if (ctx) {
      try {
        await ctx.close()
      } catch {
        /* ignore */
      }
      ctx = null
    }
    nextTime = 0
    sentenceSamples = 0
  }

  return {
    enqueueBase64Pcm,
    beginSentence,
    endSentenceDurationMs,
    captureSentenceDurationMs,
    queuedUntilMs,
    stop,
  }
}

export function formatDuration(ms) {
  if (ms == null || Number.isNaN(ms)) return '—'
  const s = ms / 1000
  if (s < 10) return `${s.toFixed(2)}s`
  return `${s.toFixed(1)}s`
}
