import { useTheme } from '../hooks/useTheme'

const ICONS = {
  system: '\u{1F5A5}️',
  light: '☀️',
  dark: '\u{1F319}',
}

const LABELS = {
  system: 'System theme',
  light: 'Light theme',
  dark: 'Dark theme',
}

export function ThemeToggle() {
  const { theme, cycleTheme } = useTheme()

  return (
    <button
      type="button"
      className="btn-icon"
      onClick={cycleTheme}
      aria-label={`Theme: ${LABELS[theme]}. Activate to switch.`}
      title={LABELS[theme]}
    >
      <span aria-hidden="true">{ICONS[theme]}</span>
    </button>
  )
}
