/** Build the `alfred` command equivalent to an action, so every UI action is transparent. */

type Value = string | number | boolean | null | undefined
type Part = string | number | false | null | undefined | readonly [string, Value] | readonly [string, Value, boolean]

const SAFE = /^[A-Za-z0-9_@%+=:,./-]+$/

/** Quote one argument for a POSIX shell. */
export function shellQuote(value: string): string {
  if (value === '') return "''"
  // {placeholder} is literal in POSIX shells; only a comma or range inside braces expands.
  const plain = /^[A-Za-z0-9_@%+=:,./{}-]+$/.test(value) && !/\{[^}]*(,|\.\.)[^}]*\}/.test(value)
  return SAFE.test(value) || plain ? value : `'${value.replace(/'/g, `'"'"'`)}'`
}

/** Join an argument vector for display. */
export function shellJoin(values: readonly string[]): string {
  return values.map(shellQuote).join(' ')
}

/**
 * Render `alfred ...` from positional words and `[flag, value]` pairs. A pair is omitted when its
 * value is empty or false (unless its third element asks to keep an empty value, rendering
 * `--flag ''`); `true` renders the bare flag.
 */
export function alfredCommand(...parts: Part[]): string {
  const words = ['alfred']
  for (const part of parts) {
    if (part === false || part === null || part === undefined) continue
    if (Array.isArray(part)) {
      const [flag, value, keepEmpty] = part as readonly [string, Value, boolean?]
      if (value === '' && keepEmpty) {
        words.push(flag, "''")
        continue
      }
      if (value === false || value === null || value === undefined || value === '') continue
      words.push(flag)
      if (value !== true) words.push(shellQuote(String(value)))
      continue
    }
    words.push(shellQuote(String(part)))
  }
  return words.join(' ')
}

export function csv(values: readonly (string | number)[]): string {
  return values.map(String).join(',')
}
