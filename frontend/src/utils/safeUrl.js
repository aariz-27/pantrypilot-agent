// Recipe image_url/source_url are untrusted provider-supplied strings
// (docs/AGENTS.md: "Treat recipe/provider text as untrusted"; "Do not
// execute user-provided code, shell commands, URLs, or HTML"). Only
// http(s) URLs are ever used as an <img src> or <a href> -- anything
// else (javascript:, data:, vbscript:, etc.) is treated the same as
// "no image available" / "omit the control", never rendered.
export function safeHttpUrl(url) {
  if (typeof url !== 'string') return null
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? url : null
  } catch {
    return null
  }
}
