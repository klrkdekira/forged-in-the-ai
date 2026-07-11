import { Circle, Group, Layer, Stage, Text } from 'react-konva'

import { layoutInRing } from '@/lib/map-layout'

const WIDTH = 260
const HEIGHT = 180

// FR-29: a district map as a shared fiction aid - not a measured grid
// (§3 non-goals), so a computed ring layout is enough; there's no stored
// position/adjacency data for locations yet (ADR-0007's follow-up), so
// no connecting lines are drawn between them.
export function DistrictMap({ locations }: { locations: string[] }) {
  if (locations.length === 0) {
    return <p className="text-xs text-muted-foreground">No locations yet.</p>
  }

  const points = layoutInRing(locations.length, { width: WIDTH, height: HEIGHT })

  return (
    <Stage width={WIDTH} height={HEIGHT}>
      <Layer>
        {locations.map((name, index) => (
          <Group key={name} x={points[index].x} y={points[index].y}>
            <Circle radius={6} fill="#6b7280" />
            <Text text={name} fontSize={10} fill="#6b7280" x={10} y={-5} />
          </Group>
        ))}
      </Layer>
    </Stage>
  )
}
