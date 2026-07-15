/** Shared agent names and emoji — use real UTF-8, not Python-style \\U escapes. */

export const AGENT_NAMES = ['cici咪', 'coco咪', 'soso咪']

export const AGENT_EMOJI = {
  'cici咪': '🏗️',
  'coco咪': '⚡',
  'soso咪': '🔍',
}

export const AGENT_INFO = {
  'cici咪': { emoji: '🏗️', border: 'border-blue-400', nameColor: 'text-blue-600', role: '架构师', desc: '架构师' },
  'coco咪': { emoji: '⚡', border: 'border-green-400', nameColor: 'text-green-600', role: '全栈开发', desc: '全栈开发' },
  'soso咪': { emoji: '🔍', border: 'border-purple-400', nameColor: 'text-purple-600', role: 'QA', desc: 'QA' },
}

export const UI_EMOJI = {
  robot: '🤖',
  folder: '📁',
  clipboard: '📋',
  wrench: '🔧',
  refresh: '🔄',
  check: '✅',
  cross: '❌',
  hourglass: '⏳',
  thinking: '💭',
  human: '🧑',
  rocket: '🚀',
  paperclip: '📎',
  speech: '💬',
  warning: '⚠️',
  fallback: '🤖',
}

export const CHAT_PLACEHOLDER =
  '发送消息到 TeamChat... (@cici咪 @coco咪 @soso咪)'

export const WELCOME_MESSAGE =
  '欢迎来到 TeamChat！使用 @cici咪 @coco咪 @soso咪 向 agent 发送消息。'
