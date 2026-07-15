import { useState, useRef, useCallback, useEffect } from 'react'
import { AGENT_NAMES, AGENT_INFO, UI_EMOJI, CHAT_PLACEHOLDER } from '../constants/agents.js'

const AGENTS = AGENT_NAMES.map((name) => ({
  name,
  emoji: AGENT_INFO[name].emoji,
  desc: AGENT_INFO[name].desc,
}))

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [showM, setShowM] = useState(false)
  const [mFilter, setMFilter] = useState('')
  const [selIdx, setSelIdx] = useState(0)
  const [sending, setSending] = useState(false)
  const [isComp, setIsComp] = useState(false)
  const [files, setFiles] = useState([])
  const taRef = useRef(null)
  const mRef = useRef(null)
  const fileRef = useRef(null)

  const filtered = AGENTS.filter((a) => a.name.includes(mFilter))
  const closeM = useCallback(() => { setShowM(false); setSelIdx(0) }, [])

  const handleChange = useCallback((e) => {
    const v = e.target.value; setText(v)
    const pos = e.target.selectionStart
    const m = v.slice(0, pos).match(/@([^\s@]*)$/)
    if (m && !isComp) { setShowM(true); setMFilter(m[1]); setSelIdx(0) } else setShowM(false)
  }, [isComp])

  const onCompStart = useCallback(() => setIsComp(true), [])
  const onCompEnd = useCallback((e) => {
    setIsComp(false)
    const pos = e.target.selectionStart
    const m = e.target.value.slice(0, pos).match(/@([^\s@]*)$/)
    if (m) { setShowM(true); setMFilter(m[1]); setSelIdx(0) }
  }, [])

  const selectM = useCallback((name) => {
    const ta = taRef.current; if (!ta) return
    const pos = ta.selectionStart
    const before = text.slice(0, pos), after = text.slice(pos)
    const replaced = before.replace(/@[^\s@]*$/, '@' + name + ' ')
    setText(replaced + after); closeM(); ta.focus()
    const np = replaced.length; requestAnimationFrame(() => ta.setSelectionRange(np, np))
  }, [text, closeM])

  const handleKeyDown = useCallback((e) => {
    if (showM && filtered.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelIdx(i => Math.min(i + 1, filtered.length - 1)); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelIdx(i => Math.max(i - 1, 0)); return }
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); selectM(filtered[selIdx].name); return }
      if (e.key === 'Escape') { closeM(); return }
    }
    if (e.key === 'Enter' && !e.shiftKey && !isComp) { e.preventDefault(); doSend() }
  }, [showM, filtered, selIdx, isComp])

  const doSend = useCallback(async () => {
    const t = text.trim(); if (!t || sending || disabled) return
    setSending(true)
    try {
      let payload = t
      if (files.length > 0) { payload = t + '\n\n[Attachment]\n' + files.map(f => f.path || f.name).join('\n') }
      await onSend(payload); setText(''); setFiles([])
    } finally { setSending(false) }
  }, [text, sending, disabled, onSend, files])

  useEffect(() => {
    if (!showM) return
    const h = (e) => { if (mRef.current && !mRef.current.contains(e.target)) closeM() }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [showM, closeM])

  const handleAttach = useCallback(() => fileRef.current?.click(), [])
  const handleFiles = useCallback((e) => { setFiles(p => [...p, ...Array.from(e.target.files || [])].slice(0, 5)); e.target.value = '' }, [])

  return (
    <div className="relative border-t border-gray-200 bg-white px-4 pt-3 pb-3">
      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {files.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-600">
              {UI_EMOJI.paperclip} {f.name}
              <button onClick={() => setFiles(p => p.filter((_, j) => j !== i))} className="text-gray-400 hover:text-gray-600 ml-0.5">&times;</button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          {showM && filtered.length > 0 && (
            <div ref={mRef} className="absolute bottom-full left-0 mb-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-20 min-w-[180px]">
              {filtered.map((a, i) => (
                <button key={a.name} className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${i === selIdx ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}
                  onMouseDown={(e) => { e.preventDefault(); selectM(a.name) }}>
                  <span>{a.emoji}</span><span className="font-medium">@{a.name}</span><span className="text-xs text-gray-400">{a.desc}</span>
                </button>
              ))}
            </div>
          )}
          <textarea ref={taRef} value={text} onChange={handleChange} onKeyDown={handleKeyDown}
            onCompositionStart={onCompStart} onCompositionEnd={onCompEnd}
            placeholder={CHAT_PLACEHOLDER} rows={1} disabled={disabled || sending}
            className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-700 placeholder-gray-400 resize-none outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200 transition-colors disabled:bg-gray-100 disabled:text-gray-400"
            style={{ minHeight: '42px', maxHeight: '120px' }}
            onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px' }} />
        </div>
        <button onClick={handleAttach} disabled={disabled}
          className="flex-shrink-0 bg-gray-100 hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-300 text-gray-500 rounded-xl px-3 py-2.5 text-sm transition-colors" title="Attach">{UI_EMOJI.paperclip}</button>
        <input ref={fileRef} type="file" multiple className="hidden" onChange={handleFiles} />
        <button onClick={doSend} disabled={!text.trim() || sending || disabled}
          className="flex-shrink-0 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-200 disabled:text-gray-400 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors flex items-center gap-1.5">
          {sending ? <><span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white/80 rounded-full animate-spin" /> Sending</> : <>{UI_EMOJI.speech} Send</>}
        </button>
      </div>
      <div className="mt-1.5 text-[10px] text-gray-400 flex items-center gap-3">
        <span>Enter send · Shift+Enter newline</span>
        <span>@ mention</span>
        <span>{UI_EMOJI.paperclip} attach</span>
      </div>
    </div>
  )
}
