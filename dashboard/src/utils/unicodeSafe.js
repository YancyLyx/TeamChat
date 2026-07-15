/**
 * Decode raw Unicode escape sequences in text strings.
 *
 * Handles:
 * - \uXXXX (standard 4-hex-digit JSON/JS escapes)
 * - \UXXXXXXXX (Python repr format for non-BMP characters)
 * - Surrogate pairs \uXXXX\uXXXX
 *
 * This is a safety net for any escape sequences that might slip through
 * from backend serialization (ensure_ascii=True) or CLI output.
 */
export function decodeUnicode(text) {
  if (!text || typeof text !== 'string') return text

  // Decode \UXXXXXXXX (Python repr format, 8 hex digits)
  // Replace literal backslash-U-8hexdigits with actual char
  let result = text.replace(/\\([Uu])0?([0-9a-fA-F]{4,8})/g, (match, prefix, hex) => {
    try {
      const codePoint = parseInt(hex, 16)
      if (codePoint > 0x10FFFF) return match
      return String.fromCodePoint(codePoint)
    } catch {
      return match
    }
  })

  return result
}
