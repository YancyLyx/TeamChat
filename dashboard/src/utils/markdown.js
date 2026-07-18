import { marked } from 'marked'

function escapeHtml(value) {
  if (typeof value !== 'string') return ''
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

marked.use({
  renderer: {
    html({ text }) {
      return escapeHtml(text)
    },
  },
})

export function sanitize(html) {
  if (typeof html !== 'string') return ''
  return html
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?>[\s\S]*?<\/iframe>/gi, '')
    .replace(/<embed[\s\S]*?>[\s\S]*?<\/embed>/gi, '')
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, '')
    .replace(/<(object|meta|link|base|form|svg|math|video|audio)[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<(object|meta|link|base|form|input|svg|math|video|audio)[^>]*\/?>/gi, '')
    .replace(/\bon\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\bon\w+\s*=\s*'[^']*'/gi, '')
    .replace(/\bon\w+\s*=\s*[^\s>]+/gi, '')
    .replace(/href\s*=\s*"javascript:[^"]*"/gi, 'href="#"')
    .replace(/href\s*=\s*'javascript:[^']*'/gi, "href='#'")
    .replace(/href\s*=\s*javascript:[^\s>]+/gi, 'href="#"')
    .replace(/src\s*=\s*"javascript:[^"]*"/gi, 'src=""')
    .replace(/src\s*=\s*'javascript:[^']*'/gi, "src=''")
    .replace(/src\s*=\s*javascript:[^\s>]+/gi, 'src=""')
}

export function mdRender(text) {
  if (!text || typeof text !== 'string') return ''
  try {
    return sanitize(marked.parse(text, { async: false, breaks: true }) || '')
  } catch {
    return escapeHtml(text)
  }
}
