/** Markdown rendering for prompts, plans, knowledge, and tracker files (raw HTML disabled). */

import MarkdownIt from 'markdown-it'

const renderer = new MarkdownIt({ html: false, linkify: true, breaks: false, typographer: false })

const defaultLink =
  renderer.renderer.rules.link_open ??
  ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))

renderer.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLink(tokens, index, options, env, self)
}

export function renderMarkdown(source: string): string {
  return renderer.render(source ?? '')
}

/** Render inline Markdown (for one-line notes). */
export function renderInline(source: string): string {
  return renderer.renderInline(source ?? '')
}
