/**
 * Convert terminal output that uses ANSI SGR sequences (as `tmux capture-pane -e` produces) into
 * escaped HTML spans. Other control sequences are dropped.
 */

interface Style {
  fg: string | null
  bg: string | null
  bold: boolean
  dim: boolean
  italic: boolean
  underline: boolean
  inverse: boolean
  strike: boolean
}

const EMPTY: Style = {
  fg: null,
  bg: null,
  bold: false,
  dim: false,
  italic: false,
  underline: false,
  inverse: false,
  strike: false,
}

// Matches CSI sequences, OSC sequences (BEL or ST terminated), and single-character escapes.
const SEQUENCE = /\x1b\[([0-9;:?]*)([A-Za-z@`])|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\x1b[=>78DEHMNOZc]/g

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (character) => {
    switch (character) {
      case '&':
        return '&amp;'
      case '<':
        return '&lt;'
      case '>':
        return '&gt;'
      case '"':
        return '&quot;'
      default:
        return '&#39;'
    }
  })
}

/** Remove every escape sequence, leaving plain text. */
export function stripAnsi(text: string): string {
  return text.replace(SEQUENCE, '').replace(/\r/g, '')
}

function color256(index: number): string {
  if (index < 16) return `var(--ansi-${index})`
  if (index < 232) {
    const value = index - 16
    const levels = [0, 95, 135, 175, 215, 255]
    const red = levels[Math.floor(value / 36)]
    const green = levels[Math.floor(value / 6) % 6]
    const blue = levels[value % 6]
    return `rgb(${red} ${green} ${blue})`
  }
  const gray = 8 + (index - 232) * 10
  return `rgb(${gray} ${gray} ${gray})`
}

function applyCodes(style: Style, raw: string): Style {
  const next = { ...style }
  const codes = raw === '' ? [0] : raw.split(/[;:]/).map((item) => (item === '' ? 0 : Number(item)))
  for (let index = 0; index < codes.length; index += 1) {
    const code = codes[index]
    if (code === 0) Object.assign(next, EMPTY)
    else if (code === 1) next.bold = true
    else if (code === 2) next.dim = true
    else if (code === 3) next.italic = true
    else if (code === 4) next.underline = true
    else if (code === 7) next.inverse = true
    else if (code === 9) next.strike = true
    else if (code === 22) {
      next.bold = false
      next.dim = false
    } else if (code === 23) next.italic = false
    else if (code === 24) next.underline = false
    else if (code === 27) next.inverse = false
    else if (code === 29) next.strike = false
    else if (code >= 30 && code <= 37) next.fg = `var(--ansi-${code - 30})`
    else if (code >= 90 && code <= 97) next.fg = `var(--ansi-${code - 90 + 8})`
    else if (code >= 40 && code <= 47) next.bg = `var(--ansi-${code - 40})`
    else if (code >= 100 && code <= 107) next.bg = `var(--ansi-${code - 100 + 8})`
    else if (code === 39) next.fg = null
    else if (code === 49) next.bg = null
    else if (code === 38 || code === 48) {
      const mode = codes[index + 1]
      let value: string | null = null
      if (mode === 5 && index + 2 < codes.length) {
        value = color256(codes[index + 2])
        index += 2
      } else if (mode === 2 && index + 4 < codes.length) {
        value = `rgb(${codes[index + 2]} ${codes[index + 3]} ${codes[index + 4]})`
        index += 4
      }
      if (value !== null) {
        if (code === 38) next.fg = value
        else next.bg = value
      }
    }
  }
  return next
}

function styleAttribute(style: Style): string {
  const fg = style.inverse ? (style.bg ?? 'var(--screen)') : style.fg
  const bg = style.inverse ? (style.fg ?? 'var(--screen-ink)') : style.bg
  const rules: string[] = []
  if (fg) rules.push(`color:${fg}`)
  if (bg) rules.push(`background:${bg}`)
  if (style.bold) rules.push('font-weight:700')
  if (style.dim) rules.push('opacity:.62')
  if (style.italic) rules.push('font-style:italic')
  const decorations = [style.underline ? 'underline' : '', style.strike ? 'line-through' : ''].filter(Boolean)
  if (decorations.length) rules.push(`text-decoration:${decorations.join(' ')}`)
  return rules.join(';')
}

/** Render ANSI-coloured text to HTML. The result only contains escaped text and span tags. */
export function ansiToHtml(text: string): string {
  let style: Style = { ...EMPTY }
  let html = ''
  let last = 0
  const flush = (chunk: string) => {
    if (!chunk) return
    const escaped = escapeHtml(chunk.replace(/\r/g, ''))
    const css = styleAttribute(style)
    html += css ? `<span style="${css}">${escaped}</span>` : escaped
  }
  SEQUENCE.lastIndex = 0
  for (let match = SEQUENCE.exec(text); match !== null; match = SEQUENCE.exec(text)) {
    flush(text.slice(last, match.index))
    if (match[2] === 'm') style = applyCodes(style, match[1] ?? '')
    last = SEQUENCE.lastIndex
  }
  flush(text.slice(last))
  return html
}
