// Purely decorative culinary still-life imagery -- never presented as
// or implied to be recipe imagery, never claiming provenance of any
// specific returned recipe. Source assets are Founder-provided,
// pre-approved photos: src/assets/backgrounds/pantrypilot-bg-{left,
// right}.png (originals, kept for provenance) with a compressed
// pantrypilot-bg-{left,right}.webp derivative alongside them (the one
// actually referenced from CSS) -- not duplicated anywhere else.
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
      <div className="hero-decor__glow hero-decor__glow--lower-left" />
      <div className="hero-decor__glow hero-decor__glow--lower-right" />
      <div className="hero-decor__panel hero-decor__panel--left" />
      <div className="hero-decor__panel hero-decor__panel--right" />
      {/* Restrained visual branding only -- never functional, never
          read by assistive tech (the whole tree is aria-hidden), and
          only shown on wide desktop (see App.css). */}
      <p className="hero-decor__caption hero-decor__caption--left">
        Great Meals
        <br />
        Start Here
      </p>
      <p className="hero-decor__caption hero-decor__caption--right">
        Simple
        <br />
        Ingredients
        <br />
        Extraordinary
        <br />
        Meals
      </p>
    </div>
  )
}
