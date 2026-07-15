
import ApprovalCard from './ApprovalCard.jsx'
import { AGENT_EMOJI, UI_EMOJI } from '../constants/agents.js'
import { decodeUnicode } from '../utils/unicodeSafe.js'

const AGENT_BORDERS = {
  'cici咪': 'border-blue-400',
  'coco咪': 'border-green-400',
  'soso咪': 'border-purple-400',
}

function ft(iso) {
  try { return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return iso }
}

function hlM(text) {
  text = decodeUnicode(text)
  if (!text) return null
  const parts = text.split(/(@(?:cici咪|coco咪|soso咪))/g)
  const cs = { 'cici咪': 'bg-blue-100 text-blue-700', 'coco咪': 'bg-green-100 text-green-700', 'soso咪': 'bg-purple-100 text-purple-700' }
  return parts.map((p, i) => p.startsWith('@') ? <span key={i} className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${cs[p.slice(1)] || 'bg-gray-100 text-gray-600'}`}>{p}</span> : p)
}

function ps(text) {
  if (!text || typeof text !== 'string') return [{ type: 'text', content: text || '' }]
  const lines = text.split('\n'), segs = []
  let cur = [], mode = 'text', heading = ''
  const flush = (nm) => { if (cur.length) { const j = cur.join('\n'); segs.push(mode === 'text' ? { type: 'text', content: j } : { type: mode, heading, content: j }) }; cur = []; mode = nm }
  for (const line of lines) {
    const t = line.trim()
    if (/^THINKING\s*:/i.test(t)) { flush('thinking'); heading = 'THINKING'; const r = line.slice(line.indexOf(':') + 1).trim(); if (r) cur.push(r) }
    else if (/^TOOL_CALLS\s*:/i.test(t)) { flush('tool_calls'); heading = 'TOOL_CALLS'; const r = line.slice(line.indexOf(':') + 1).trim(); if (r) cur.push(r) }
    else cur.push(line)
  }
  flush('text')
  return segs
}

function RS({ text, tss }) {
  if (tss && tss.length > 0) {
    return (<div className="space-y-2">
      {tss.map((sec, i) => <details key={i} className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden"><summary className="flex items-center gap-2 px-3 py-2 text-xs font-mono cursor-pointer hover:bg-gray-100 select-none text-gray-500"><span>{UI_EMOJI.thinking}</span><span className="font-semibold text-gray-600">THINKING</span><span className="ml-auto text-gray-300 text-[10px]">expand/collapse</span></summary><div className="px-3 pb-2 pt-1 text-xs text-gray-500 font-mono leading-relaxed whitespace-pre-wrap border-t border-gray-100">{sec}</div></details>)}
      <div className="whitespace-pre-wrap">{hlM(text)}</div>
    </div>)
  }
  const segs = ps(text)
  if (segs.length === 1 && segs[0].type === 'text') return <span className="whitespace-pre-wrap">{hlM(segs[0].content)}</span>
  return (<div className="space-y-2">{segs.map((seg, i) => {
    if (seg.type === 'text') return <div key={i} className="whitespace-pre-wrap">{hlM(seg.content)}</div>
    return (<details key={i} className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden"><summary className="flex items-center gap-2 px-3 py-2 text-xs font-mono cursor-pointer hover:bg-gray-100 select-none text-gray-500"><span>{seg.type === 'thinking' ? UI_EMOJI.thinking : UI_EMOJI.wrench}</span><span className="font-semibold text-gray-600">{seg.heading}</span><span className="ml-auto text-gray-300 text-[10px]">expand/collapse</span></summary><div className="px-3 pb-2 pt-1 text-xs text-gray-500 font-mono leading-relaxed whitespace-pre-wrap border-t border-gray-100">{seg.content}</div></details>)
  })}</div>)
}

export default function ChatMessage({ message }) {
  const { kind, agent, content, timestamp, thinking_sections, tool_name, tool_input, onApprove, onDeny } = message

  if (kind === 'human') {
    return (
      <div className="flex justify-end mb-3 msg-animate">
        <div className="max-w-[75%] min-w-[100px]">
          <div className="flex items-center justify-end gap-2 mb-1">
            <span className="text-[10px] text-gray-400 font-mono">{ft(timestamp)}</span>
            <span className="text-xs text-gray-500 font-medium">你</span>
            <span className="text-sm">{UI_EMOJI.human}</span>
          </div>
          <div className="bg-blue-500 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words shadow-sm">{content}</div>
        </div>
      </div>
    )
  }

  if (kind === 'agent' || kind === 'agent_reply' || kind === 'agent_message' || (kind === undefined && agent)) {
    const border = AGENT_BORDERS[agent] || 'border-gray-300'
    const emoji = AGENT_EMOJI[agent] || UI_EMOJI.fallback
    return (
      <div className="flex justify-start mb-3 msg-animate">
        <div className="max-w-[75%] min-w-[100px]">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm">{emoji}</span>
            <span className="text-xs font-medium text-gray-700">{agent}</span>
            <span className="text-[10px] text-gray-400 font-mono">{ft(timestamp)}</span>
          </div>
          <div className={`bg-gray-50 border-l-2 ${border} rounded-xl rounded-tl-sm px-4 py-2.5 text-sm text-gray-700 leading-relaxed break-words shadow-sm`}>
            <RS text={content} tss={thinking_sections} />
          </div>
        </div>
      </div>
    )
  }

  if (kind === 'system') {
    return <div className="flex justify-center mb-3 msg-animate"><div className="text-xs text-gray-400 italic max-w-[80%] text-center">{content}</div></div>
  }

  if (kind === 'approval') {
    return (
      <div className="flex justify-center mb-3 msg-animate">
        <ApprovalCard tool_name={tool_name} tool_input={tool_input} agent={agent} onApprove={onApprove} onDeny={onDeny} />
      </div>
    )
  }

  if (kind === 'thinking') {
    return (
      <div className="flex justify-start mb-2 msg-animate">
        <details className="bg-gray-50 border border-gray-200 rounded-lg max-w-[75%] overflow-hidden">
          <summary className="flex items-center gap-2 px-3 py-2 text-xs font-mono cursor-pointer hover:bg-gray-100 select-none text-gray-400 italic">
            <span>{UI_EMOJI.thinking}</span> THINKING <span className="ml-auto text-gray-300 text-[10px] not-italic">expand</span>
          </summary>
          <div className="px-3 pb-2 pt-1 text-xs text-gray-500 font-mono leading-relaxed whitespace-pre-wrap border-t border-gray-100">{content}</div>
        </details>
      </div>
    )
  }

  if (kind === 'task_event') {
    return (
      <div className="flex justify-start mb-1.5 pl-2 msg-animate">
        <div className="flex items-center gap-2 text-xs text-gray-400 font-mono">
          <span>{message.type === 'task_started' ? UI_EMOJI.rocket : UI_EMOJI.check}</span>
          <span className="text-gray-500">{agent}</span>
          <span className="text-gray-300">|</span>
          <span className="truncate max-w-[300px]">{content}</span>
        </div>
      </div>
    )
  }

  return <div className="flex justify-start mb-3 msg-animate"><div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-500">{content || JSON.stringify(message)}</div></div>
}
