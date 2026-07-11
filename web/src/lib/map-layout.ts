export interface MapPoint {
  x: number
  y: number
}

// FR-29: district/score maps and the claim map are fiction aids, not a
// measured grid (SPECIFICATION.md §3 non-goals: "not a tactical VTT") -
// there's no stored position or adjacency data for locations/claims
// (ADR-0007's follow-up work, not done yet), so positions are computed,
// not authored. A ring layout needs nothing from the data itself beyond
// a count, and never overlaps regardless of how many items there are.
export function layoutInRing(
  count: number,
  { width, height, padding = 24 }: { width: number; height: number; padding?: number },
): MapPoint[] {
  const centerX = width / 2
  const centerY = height / 2
  const radius = Math.max(0, Math.min(width, height) / 2 - padding)

  if (count <= 0) return []
  if (count === 1) return [{ x: centerX, y: centerY }]

  return Array.from({ length: count }, (_, index) => {
    const angle = (index / count) * 2 * Math.PI - Math.PI / 2
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    }
  })
}
