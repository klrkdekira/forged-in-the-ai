import { Circle, Group, Layer, Stage, Text } from 'react-konva'

import type { ClaimSnapshot } from '@/hooks/use-session-socket'
import { layoutInRing } from '@/lib/map-layout'

const WIDTH = 260
const HEIGHT = 180

// FR-29: the crew's claim map as a shared fiction aid - same computed
// ring layout as the district map (no stored claim positions yet).
// Controlled claims are filled; contested ones are an outline only.
// Turf gets a second ring, matching the sheet panel's existing pattern
// of encoding state through shape rather than colour alone.
export function ClaimMap({ claims }: { claims: ClaimSnapshot[] }) {
  if (claims.length === 0) {
    return <p className="text-xs text-muted-foreground">No claims yet.</p>
  }

  const points = layoutInRing(claims.length, { width: WIDTH, height: HEIGHT })

  return (
    <Stage width={WIDTH} height={HEIGHT}>
      <Layer>
        {claims.map((claim, index) => (
          <Group key={claim.id} x={points[index].x} y={points[index].y}>
            {claim.is_turf && (
              <Circle radius={9} stroke="#171717" strokeWidth={1} dash={[2, 2]} />
            )}
            <Circle
              radius={6}
              fill={claim.controlled ? '#16a34a' : undefined}
              stroke={claim.controlled ? undefined : '#ef4444'}
              strokeWidth={claim.controlled ? 0 : 1.5}
            />
            <Text text={claim.name} fontSize={10} fill="#6b7280" x={10} y={-5} />
          </Group>
        ))}
      </Layer>
    </Stage>
  )
}
