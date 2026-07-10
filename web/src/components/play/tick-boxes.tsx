// Shared clickable-track control for FR-28/FR-29 (stress, XP, clocks):
// clicking a box sets the track to that many segments marked, and clicking
// the currently-last marked box unmarks it.
export function TickBoxes({
  segments,
  marked,
  onSetMarked,
}: {
  segments: number
  marked: number
  onSetMarked: (marked: number) => void
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {Array.from({ length: segments }, (_, index) => {
        const filled = index < marked
        return (
          <button
            key={index}
            type="button"
            aria-label={`box ${index + 1}${filled ? ' (marked)' : ''}`}
            aria-pressed={filled}
            onClick={() => onSetMarked(index + 1 === marked ? index : index + 1)}
            className={`size-4 rounded-sm border transition-colors ${
              filled ? 'border-primary bg-primary' : 'border-input bg-transparent'
            }`}
          />
        )
      })}
    </div>
  )
}
