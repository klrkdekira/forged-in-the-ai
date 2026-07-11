import { describe, expect, it } from 'vitest'

import { layoutInRing } from './map-layout'

describe('layoutInRing', () => {
  it('returns nothing for zero items', () => {
    expect(layoutInRing(0, { width: 200, height: 200 })).toEqual([])
  })

  it('places a single item at the center', () => {
    const [point] = layoutInRing(1, { width: 200, height: 100 })
    expect(point).toEqual({ x: 100, y: 50 })
  })

  it('spaces items evenly around the ring', () => {
    const points = layoutInRing(4, { width: 200, height: 200, padding: 0 })

    expect(points).toHaveLength(4)
    // top, right, bottom, left (within floating-point tolerance)
    expect(points[0].x).toBeCloseTo(100)
    expect(points[0].y).toBeCloseTo(0)
    expect(points[1].x).toBeCloseTo(200)
    expect(points[1].y).toBeCloseTo(100)
    expect(points[2].x).toBeCloseTo(100)
    expect(points[2].y).toBeCloseTo(200)
    expect(points[3].x).toBeCloseTo(0)
    expect(points[3].y).toBeCloseTo(100)
  })

  it('never places a point outside the given bounds', () => {
    const points = layoutInRing(9, { width: 260, height: 180, padding: 20 })

    for (const point of points) {
      expect(point.x).toBeGreaterThanOrEqual(0)
      expect(point.x).toBeLessThanOrEqual(260)
      expect(point.y).toBeGreaterThanOrEqual(0)
      expect(point.y).toBeLessThanOrEqual(180)
    }
  })
})
