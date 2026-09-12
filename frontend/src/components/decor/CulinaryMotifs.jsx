// Purely decorative, locally-authored culinary still-life imagery --
// never a photo of a real dish, never presented as or implied to be
// recipe imagery, never claiming provenance of any specific returned
// recipe (ticket: no external stock photography, no scraping, no
// fabricated recipe images). Rendered as vector art and rasterized to
// WebP locally (src/assets/decor/source/*.svg has the originals) so
// there is no licensing question at all, unlike a sourced photograph.
//
// The actual background-image URLs live in App.css, not here: a CSS
// background-image inside a media query is only fetched by the
// browser when that query matches, which is how mobile avoids
// downloading these entirely (ticket: "do not block initial rendering
// unnecessarily" / mobile may disappear entirely) -- a JS-driven
// inline style would fetch regardless of viewport width.
export function HeroDecor() {
  return (
    <div className="hero-decor" aria-hidden="true">
      <div className="hero-decor__glow hero-decor__glow--left" />
      <div className="hero-decor__glow hero-decor__glow--right" />
      <div className="hero-decor__panel hero-decor__panel--left" />
      <div className="hero-decor__panel hero-decor__panel--right" />
    </div>
  )
}
