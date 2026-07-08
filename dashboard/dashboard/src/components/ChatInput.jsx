import { useState, useRef, useCallback, useEffect } from 'react'

const AGENT_NAMES = ['cici咪', 'coco咪', 'soso咪']
const MENTION_RE = /@(cici咪|coco咪|soso咪)/g

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [mentionFilter, setMentionFilter] = useState('')
  const [sending, setSending] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const textareaRef = useRef(null)
  const mentionRef = useRef(null)

  // Handle input changes
  const handleChange = useCallback((e) => {
    const value = e.target.value
    setText(value)

    // Check for @mention trigger
    const cursorPos = e.target.selectionStart
    const beforeCursor = value.slice(0, cursorPos)
    const atMatch = beforeCursor.match(/@([^\s@]*)$/)
    if (atMatch) {
      setShowMentions(true)
      setMentionFilter(atMatch[1])
    } else {
      setShowMentions(false)
    }
  }, [])

  // Select a mention from the dropdown
  const selectMention = useCallback((name) => {
    const ta = textareaRef.current
    if (!ta) return
    const cursorPos = ta.selectionStart
    const beforeCursor = text.slice(0, cursorPos)
    const afterCursor = text.slice(cursorPos)
    const beforeMatch = beforeCursor.replace(/@[^\s@]*$/, `@${name} `)
    setText(beforeMatch + afterCursor)
    setShowMentions(false)
    ta.focus()
  }, [text])

  // Send the message
  const handleSend = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed || sending || disabled) return

    setSending(true)
    try {
      await onSend(trimmed)
      setText('')
    } finally {
      setSending(false)
    }
  }, [text, sending, disabled, onSend])

  // Handle keyboard
  const handleKeyDown = useCallback((e) => {
    if (showMentions && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter')) {
      // Let the mention dropdown handle these keys
      if (e.key === 'Enter') return
    }
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault()
      handleSend()
    }
  }, [showMentions, handleSend, isComposing])

  // Filter agents for mention dropdown
  const filteredAgents = AGENT_NAMES.filter((a) =>
    a.includes(mentionFilter) || mentionFilter === ''
  )

  // Close mentions on click outside
  useEffect(() => {
    if (!showMentions) return
    const handler = (e) => {
      if (mentionRef.current && !mentionRef.current.contains(e.target)) {
        setShowMentions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showMentions])

  return (
    <div className="relative border-t border-gray-800/60 bg-gray-950/95 px-4 py-3">
      {/* Mention dropdown */}
      {showMentions && filteredAgents.length > 0 && (
        <div
          ref={mentionRef}
          className="absolute bottom-full left-4 mb-1 bg-gray-800 border border-gray-700/60 rounded-lg shadow-lg overflow-hidden z-20"
        >
          {filteredAgents.map((name) => (
            <button
              key={name}
              className="block w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-gray-700/60 transition-colors"
              onMouseDown={(e) => { e.preventDefault(); selectMention(name) }}
            >
              @{name}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={() => setIsComposing(false)}
            placeholder="发送消息到 TeamChat... (@cici咪 @coco咪 @soso咪)"
            rows={1}
            disabled={disabled}
            className="w-full bg-gray-900/80 border border-gray-700/50 rounded-xl px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 resize-none outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-colors"
            style={{ minHeight: '42px', maxHeight: '120px' }}
            onInput={(e) => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
          />
        </div>

        <button
          onClick={handleSend}
          disabled={!text.trim() || sending || disabled}
          className="flex-shrink-0 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors flex items-center gap-1.5"
        >
          {sending ? (
            <>
              <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white/80 rounded-full animate-spin" />
              发送中
            </>
          ) : (
            <>
              <span>💬</span>
              发送
            </>
          )}
        </button>
      </div>

      {/* Hint */}
      <div className="mt-1.5 text-[10px] text-gray-600 flex items-center gap-3">
        <span>Enter 发送 · Shift+Enter 换行 · 中文输入时 Enter 不发送</span>
        <span>@ 提及 agent</span>
      </div>
    </div>
  )
}
