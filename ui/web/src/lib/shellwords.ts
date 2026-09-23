/** Split a shell-like command line into an argument array (quotes and backslashes only). */
export function splitCommand(line: string): string[] {
  const words: string[] = []
  let current = ''
  let quote: '"' | "'" | null = null
  let started = false
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index]
    if (quote === "'") {
      if (character === "'") quote = null
      else current += character
      continue
    }
    if (quote === '"') {
      if (character === '"') quote = null
      else if (character === '\\' && index + 1 < line.length && '"\\$`'.includes(line[index + 1])) current += line[++index]
      else current += character
      continue
    }
    if (character === "'" || character === '"') {
      quote = character
      started = true
    } else if (character === '\\' && index + 1 < line.length) {
      current += line[++index]
      started = true
    } else if (/\s/.test(character)) {
      if (started) words.push(current)
      current = ''
      started = false
    } else {
      current += character
      started = true
    }
  }
  if (quote) throw new Error('Unclosed quote in the command')
  if (started) words.push(current)
  return words
}
