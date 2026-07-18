#!/usr/bin/env node
/** Unit checks for dashboard/src/utils/markdown.js (run via pytest). */
import { mdRender, sanitize } from '../src/utils/markdown.js'

let failed = 0

function assert(cond, msg) {
  if (!cond) {
    console.error(`FAIL: ${msg}`)
    failed += 1
  }
}

const bold = mdRender('**hello**')
assert(bold.includes('<strong>'), 'markdown bold should render')
assert(bold.includes('hello'), 'markdown bold keeps text')

const xssScript = mdRender('**x** <script>alert(1)</script>')
assert(!xssScript.toLowerCase().includes('<script'), 'script tag must not be raw HTML')
assert(xssScript.includes('&lt;script&gt;'), 'inline HTML should be escaped')

const xssImg = mdRender('<img src=x onerror=alert(1)>')
assert(!/onerror/i.test(xssImg), 'onerror handler must be stripped')
assert(!xssImg.includes('alert(1)'), 'inline handler payload must not survive')

const jsHref = mdRender('[click](javascript:alert(1))')
assert(!jsHref.toLowerCase().includes('javascript:'), 'javascript: links must be neutralized')

const rawHtml = mdRender('<iframe src="evil"></iframe>')
assert(!rawHtml.toLowerCase().includes('<iframe'), 'iframe must be stripped')

const sanitized = sanitize('<a href=javascript:alert(1) onclick=alert(2)>x</a>')
assert(!sanitized.toLowerCase().includes('javascript:'), 'unquoted javascript href stripped')
assert(!/onclick/i.test(sanitized), 'unquoted onclick stripped')

if (failed) {
  process.exit(1)
}
console.log('markdown unit checks passed')
