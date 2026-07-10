import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import type { CharacterSnapshot, SheetOperation } from '@/hooks/use-session-socket'

function TickBoxes({
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

const ATTRIBUTES = ['insight', 'prowess', 'resolve'] as const

// FR-28: character stress/harm/XP/load/coin are clickable, and every click
// goes through an engine operation (`sendSheetOperation`) - never a direct
// state edit. Lives inside /play (not a separate route) because the
// GameState this reflects only exists for the lifetime of the one active
// WS connection - there's no persisted, addressable session yet to share
// across pages (that's Phase 5).
export function CharacterSheetPanel({
  character,
  onOperate,
}: {
  character: CharacterSnapshot
  onOperate: (operation: SheetOperation) => void
}) {
  const [harmLevel, setHarmLevel] = useState('1')
  const [harmName, setHarmName] = useState('')

  function submitHarm() {
    if (!harmName.trim()) return
    onOperate({
      name: 'apply_harm',
      args: { level: Number(harmLevel), name: harmName.trim() },
    })
    setHarmName('')
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      <div>
        <h2 className="text-lg font-semibold text-foreground">{character.name}</h2>
        <p className="text-xs text-muted-foreground">{character.playbook}</p>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground">Stress</span>
        <TickBoxes
          segments={9}
          marked={character.stress.marked}
          onSetMarked={(marked) =>
            onOperate({
              name: 'mark_stress',
              args: { amount: marked - character.stress.marked },
            })
          }
        />
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-muted-foreground">Harm</span>
        {character.harm.entries.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {character.harm.entries.map((entry, index) => (
              <li key={index} className="text-xs">
                <span className="font-semibold">L{entry.level}</span> {entry.name}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No harm marked.</p>
        )}
        <div className="flex gap-2">
          <select
            value={harmLevel}
            onChange={(event) => setHarmLevel(event.target.value)}
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-xs"
          >
            <option value="1">L1</option>
            <option value="2">L2</option>
            <option value="3">L3</option>
            <option value="4">L4 (fatal)</option>
          </select>
          <Input
            value={harmName}
            onChange={(event) => setHarmName(event.target.value)}
            placeholder="e.g. Twisted Ankle"
            className="h-8"
          />
          <Button type="button" size="sm" onClick={submitHarm} disabled={!harmName.trim()}>
            Mark
          </Button>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onOperate({ name: 'heal_character', args: {} })}
          disabled={character.harm.entries.length === 0}
        >
          Heal 1 level
        </Button>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground">Playbook XP</span>
        <TickBoxes
          segments={character.playbook_xp.segments}
          marked={character.playbook_xp.marked}
          onSetMarked={(marked) =>
            onOperate({
              name: 'mark_xp',
              args: { track: 'playbook', amount: marked - character.playbook_xp.marked },
            })
          }
        />
      </div>

      {ATTRIBUTES.map((attribute) => {
        const track = character.attribute_xp[attribute]
        return (
          <div key={attribute} className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-muted-foreground capitalize">
              {attribute} XP
            </span>
            <TickBoxes
              segments={track.segments}
              marked={track.marked}
              onSetMarked={(marked) =>
                onOperate({
                  name: 'mark_xp',
                  args: { track: attribute, amount: marked - track.marked },
                })
              }
            />
          </div>
        )
      })}

      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">Coin</span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={() => onOperate({ name: 'adjust_coin', args: { amount: -1 } })}
            disabled={character.coin <= 0}
          >
            -
          </Button>
          <span className="w-6 text-center">{character.coin}</span>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={() => onOperate({ name: 'adjust_coin', args: { amount: 1 } })}
          >
            +
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground">
          Load ({character.load})
        </span>
        {character.items.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {character.items.map((item) => (
              <li key={item.item_id}>
                <label className="flex items-center gap-2 text-xs">
                  <Checkbox
                    checked={item.carried}
                    onCheckedChange={(checked) =>
                      onOperate({
                        name: 'set_item_carried',
                        args: { item_id: item.item_id, carried: checked === true },
                      })
                    }
                  />
                  {item.item_id}
                </label>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No items on the sheet yet.</p>
        )}
      </div>
    </div>
  )
}
