// Purely decorative, locally-authored SVG line-art -- never a photo,
// never presented as recipe imagery, never implying provenance of any
// specific returned recipe (ticket section 8/31: no external stock
// photography, no scraping, no fabricated recipe images). Inline SVG
// keeps this at near-zero byte/network cost and lets the linework
// inherit theme color via currentColor, so it repaints correctly for
// light/dark without a second asset.

export function HerbSprigMotif(props) {
  return (
    <svg viewBox="0 0 220 520" fill="none" aria-hidden="true" focusable="false" {...props}>
      <path d="M110 20 C 104 140 116 300 110 500" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      {[70, 130, 190, 250, 310, 370, 430].map((y, i) => {
        const left = i % 2 === 0
        const x1 = 110
        const x2 = left ? 30 : 190
        const cx = left ? 60 : 160
        return (
          <path
            key={y}
            d={`M ${x1} ${y} Q ${cx} ${y - 26} ${x2} ${y - 8} Q ${cx} ${y + 22} ${x1} ${y + 34}`}
            stroke="currentColor"
            strokeWidth="1.25"
            fill="currentColor"
            fillOpacity="0.08"
          />
        )
      })}
    </svg>
  )
}

export function CitrusSliceMotif(props) {
  return (
    <svg viewBox="0 0 240 240" fill="none" aria-hidden="true" focusable="false" {...props}>
      <circle cx="120" cy="120" r="108" stroke="currentColor" strokeWidth="2" />
      <circle cx="120" cy="120" r="86" stroke="currentColor" strokeWidth="1" strokeDasharray="2 4" />
      {Array.from({ length: 10 }).map((_, i) => {
        const angle = (Math.PI * 2 * i) / 10
        const x1 = 120 + Math.cos(angle) * 34
        const y1 = 120 + Math.sin(angle) * 34
        const x2 = 120 + Math.cos(angle) * 84
        const y2 = 120 + Math.sin(angle) * 84
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth="1" />
      })}
      <circle cx="120" cy="120" r="30" stroke="currentColor" strokeWidth="1.5" fill="currentColor" fillOpacity="0.06" />
    </svg>
  )
}

export function WheatStalkMotif(props) {
  return (
    <svg viewBox="0 0 180 480" fill="none" aria-hidden="true" focusable="false" {...props}>
      <path d="M90 20 C 84 160 96 320 90 460" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      {Array.from({ length: 9 }).map((_, i) => {
        const y = 60 + i * 42
        const left = i % 2 === 0
        const dx = left ? -26 : 26
        return (
          <ellipse
            key={i}
            cx={90 + dx}
            cy={y}
            rx="14"
            ry="7"
            transform={`rotate(${left ? -28 : 28} ${90 + dx} ${y})`}
            stroke="currentColor"
            strokeWidth="1"
            fill="currentColor"
            fillOpacity="0.07"
          />
        )
      })}
    </svg>
  )
}

// Fixed left/right edge decoration for the hero -- subordinate to the
// UI (low opacity, blurred glow, pointer-events disabled), fades out
// below tablet width so mobile prioritizes usability over atmosphere
// (ticket section 27). CSS lives in App.css under .hero-decor.
export function HeroDecor() {
  return (
    <div className="hero-decor" aria-hidden="true">
      <div className="hero-decor__glow hero-decor__glow--left" />
      <div className="hero-decor__glow hero-decor__glow--right" />
      <HerbSprigMotif className="hero-decor__motif hero-decor__motif--herb" />
      <CitrusSliceMotif className="hero-decor__motif hero-decor__motif--citrus" />
      <WheatStalkMotif className="hero-decor__motif hero-decor__motif--wheat" />
    </div>
  )
}
