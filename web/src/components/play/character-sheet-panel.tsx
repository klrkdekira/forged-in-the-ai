import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import type { CharacterSnapshot, SheetOperation } from '@/hooks/use-session-socket'

import { TickBoxes } from './tick-boxes'

const ATTRIBUTE_ACTIONS = {
  insight: ['hunt', 'study', 'survey', 'tinker'],
  prowess: ['finesse', 'prowl', 'skirmish', 'wreck'],
  resolve: ['attune', 'command', 'consort', 'sway'],
} as const

const TRAUMA_CONDITIONS = [
  'cold',
  'haunted',
  'obsessed',
  'paranoid',
  'reckless',
  'soft',
  'unstable',
  'vicious',
] as const

const LOAD_CAPACITIES = {
  light: 3,
  normal: 5,
  heavy: 6,
} as const

export function CharacterSheetPanel({
  characterId,
  character,
  onOperate,
}: {
  characterId: string
  character: CharacterSnapshot
  onOperate: (operation: SheetOperation) => void
}) {
  const [harmLevel, setHarmLevel] = useState('1')
  const [harmName, setHarmName] = useState('')
  const [selectedTrauma, setSelectedTrauma] = useState<string>('cold')

  const actionRatings = character.action_ratings || {}
  const traumaConditions = character.trauma?.conditions || []
  const armor = character.armor || {
    has_armor: false,
    has_heavy_armor: false,
    has_special_armor: false,
    armor_used: false,
    heavy_armor_used: false,
    special_armor_used: false,
  }
  const loadLevel = character.load_level || 'normal'
  const loadCap = LOAD_CAPACITIES[loadLevel]
  const carriedCount = character.items.filter((i) => i.carried).length

  function submitHarm() {
    if (!harmName.trim()) return
    onOperate({
      name: 'apply_harm',
      args: { level: Number(harmLevel), name: harmName.trim(), character_id: characterId },
    })
    setHarmName('')
  }

  function submitTrauma() {
    if (!selectedTrauma) return
    onOperate({
      name: 'mark_trauma',
      args: { condition: selectedTrauma, character_id: characterId },
    })
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      {/* Header & Persona Card */}
      <div className="flex flex-col gap-1.5 rounded-lg border border-border/40 bg-muted/20 p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold tracking-tight text-foreground">
            {character.name}
            {character.alias && <span className="ml-2 text-sm font-normal text-muted-foreground">"{character.alias}"</span>}
          </h2>
          <span className="capitalize text-xs font-semibold px-2 py-0.5 rounded border border-border bg-muted/40">
            {character.playbook}
          </span>
        </div>
        {character.look && <p className="text-xs italic text-muted-foreground">{character.look}</p>}
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground mt-1">
          {character.heritage && (
            <span>
              <strong className="text-foreground font-medium">Heritage:</strong> {character.heritage}
            </span>
          )}
          {character.background && (
            <span>
              <strong className="text-foreground font-medium">Background:</strong> {character.background}
            </span>
          )}
          {character.vice && (
            <span>
              <strong className="text-foreground font-medium">Vice:</strong> {character.vice}
              {character.vice_purveyor && ` (${character.vice_purveyor})`}
            </span>
          )}
        </div>
      </div>

      {/* Stress Track */}
      <div className="flex flex-col gap-1.5 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Stress
          </span>
          <span className="text-xs font-medium text-muted-foreground">
            {character.stress.marked}/9
          </span>
        </div>
        <TickBoxes
          segments={9}
          marked={character.stress.marked}
          onSetMarked={(marked) =>
            onOperate({
              name: 'mark_stress',
              args: { amount: marked - character.stress.marked, character_id: characterId },
            })
          }
        />
        {character.trauma_pending && (
          <div className="mt-2 flex items-center justify-between gap-2 bg-destructive/10 p-2 rounded border border-destructive/30">
            <span className="text-xs font-semibold text-destructive">Stress Overflow! Pick Trauma:</span>
            <select
              value={selectedTrauma}
              onChange={(e) => setSelectedTrauma(e.target.value)}
              className="h-7 text-xs rounded border bg-background px-1"
            >
              {TRAUMA_CONDITIONS.filter((c) => !traumaConditions.includes(c)).map((c) => (
                <option key={c} value={c} className="capitalize">
                  {c}
                </option>
              ))}
            </select>
            <Button type="button" size="sm" variant="destructive" onClick={submitTrauma}>
              Mark Trauma
            </Button>
          </div>
        )}
      </div>

      {/* Trauma Badges */}
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Trauma Conditions ({traumaConditions.length}/4)
        </span>
        {traumaConditions.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {traumaConditions.map((c) => (
              <span key={c} className="capitalize text-xs font-medium px-2 py-0.5 rounded bg-destructive/20 text-destructive border border-destructive/30">
                {c}
              </span>
            ))}
            {traumaConditions.length >= 4 && (
              <span className="text-xs font-bold animate-pulse px-2 py-0.5 rounded bg-destructive text-destructive-foreground">
                RETIRED
              </span>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No trauma marked yet.</p>
        )}
      </div>

      {/* Armor Track */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Armor
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 text-[0.7rem] px-2 text-muted-foreground hover:text-foreground"
            onClick={() => onOperate({ name: 'restore_armor', args: { character_id: characterId } })}
          >
            Restore
          </Button>
        </div>
        <div className="flex flex-wrap gap-4 text-xs">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <Checkbox
              checked={armor.armor_used}
              onCheckedChange={() =>
                onOperate({
                  name: 'use_armor',
                  args: { armor_type: 'standard', character_id: characterId },
                })
              }
            />
            Standard
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <Checkbox
              checked={armor.heavy_armor_used}
              onCheckedChange={() =>
                onOperate({
                  name: 'use_armor',
                  args: { armor_type: 'heavy', character_id: characterId },
                })
              }
            />
            Heavy
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <Checkbox
              checked={armor.special_armor_used}
              onCheckedChange={() =>
                onOperate({
                  name: 'use_armor',
                  args: { armor_type: 'special', character_id: characterId },
                })
              }
            />
            Special
          </label>
        </div>
      </div>

      {/* Action Ratings (3 Attributes x 4 Actions) */}
      <div className="flex flex-col gap-3 rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Action Ratings
        </span>
        {(Object.keys(ATTRIBUTE_ACTIONS) as Array<keyof typeof ATTRIBUTE_ACTIONS>).map((attr) => {
          const track = character.attribute_xp[attr]
          return (
            <div key={attr} className="flex flex-col gap-1.5 border-t border-border/20 pt-2 first:border-0 first:pt-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold capitalize text-primary">{attr}</span>
                {track && (
                  <div className="flex items-center gap-1 text-[0.7rem] text-muted-foreground">
                    <span>XP</span>
                    <TickBoxes
                      segments={track.segments}
                      marked={track.marked}
                      onSetMarked={(marked) =>
                        onOperate({
                          name: 'mark_xp',
                          args: {
                            track: attr,
                            amount: marked - track.marked,
                            character_id: characterId,
                          },
                        })
                      }
                    />
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                {ATTRIBUTE_ACTIONS[attr].map((action) => {
                  const rating = actionRatings[action] || 0
                  return (
                    <div
                      key={action}
                      className="flex items-center justify-between rounded px-2 py-1 bg-muted/20 border border-border/30"
                    >
                      <span className="text-xs capitalize font-medium">{action}</span>
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-mono font-bold">{rating}d</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Harm & Healing */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Harm</span>
        {character.harm.entries.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {character.harm.entries.map((entry, index) => (
              <li key={index} className="flex items-center justify-between text-xs rounded bg-muted/20 px-2 py-1">
                <span>
                  <strong className="text-destructive font-bold">L{entry.level}:</strong> {entry.name}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No harm marked.</p>
        )}
        <div className="flex gap-2 mt-1">
          <select
            value={harmLevel}
            onChange={(event) => setHarmLevel(event.target.value)}
            className="h-8 rounded-lg border border-input bg-background px-2 text-xs"
          >
            <option value="1">L1 (Lesser)</option>
            <option value="2">L2 (Moderate)</option>
            <option value="3">L3 (Severe)</option>
            <option value="4">L4 (Fatal)</option>
          </select>
          <Input
            value={harmName}
            onChange={(event) => setHarmName(event.target.value)}
            placeholder="e.g. Broken Ribs"
            className="h-8 text-xs"
          />
          <Button type="button" size="sm" onClick={submitHarm} disabled={!harmName.trim()}>
            Mark
          </Button>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onOperate({ name: 'heal_character', args: { character_id: characterId } })}
          disabled={character.harm.entries.length === 0}
        >
          Heal 1 level
        </Button>
        <div className="mt-1 flex items-center justify-between rounded bg-muted/20 px-2 py-1 text-xs">
          <span className="font-semibold">Healing</span>
          <span className="text-muted-foreground">
            {character.healing_clock.filled}/{character.healing_clock.segments}
          </span>
        </div>
      </div>

      {/* Playbook XP */}
      <div className="flex flex-col gap-1 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Playbook XP
          </span>
          <span className="text-xs text-muted-foreground">
            {character.playbook_xp.marked}/{character.playbook_xp.segments}
          </span>
        </div>
        <TickBoxes
          segments={character.playbook_xp.segments}
          marked={character.playbook_xp.marked}
          onSetMarked={(marked) =>
            onOperate({
              name: 'mark_xp',
              args: {
                track: 'playbook',
                amount: marked - character.playbook_xp.marked,
                character_id: characterId,
              },
            })
          }
        />
      </div>

      {/* Coin & Stash */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Coin & Stash
          </span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span>Coin ({character.coin})</span>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() =>
                onOperate({ name: 'adjust_coin', args: { amount: -1, character_id: characterId } })
              }
              disabled={character.coin <= 0}
            >
              -
            </Button>
            <span className="w-5 text-center font-bold">{character.coin}</span>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() =>
                onOperate({ name: 'adjust_coin', args: { amount: 1, character_id: characterId } })
              }
            >
              +
            </Button>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span>Stash ({character.stash || 0}/40)</span>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() =>
                onOperate({ name: 'adjust_stash', args: { amount: -1, character_id: characterId } })
              }
              disabled={(character.stash || 0) <= 0}
            >
              -
            </Button>
            <span className="w-5 text-center font-bold">{character.stash || 0}</span>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() =>
                onOperate({ name: 'adjust_stash', args: { amount: 1, character_id: characterId } })
              }
            >
              +
            </Button>
          </div>
        </div>
      </div>

      {/* Load & Inventory */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Load ({carriedCount}/{loadCap})
          </span>
          <div className="flex gap-1">
            {(['light', 'normal', 'heavy'] as const).map((lvl) => (
              <Button
                key={lvl}
                type="button"
                variant={loadLevel === lvl ? 'default' : 'outline'}
                size="sm"
                className="h-6 text-[0.65rem] capitalize px-2"
                onClick={() =>
                  onOperate({
                    name: 'set_load_level',
                    args: { level: lvl, character_id: characterId },
                  })
                }
              >
                {lvl} ({LOAD_CAPACITIES[lvl]})
              </Button>
            ))}
          </div>
        </div>
        {character.items.length > 0 ? (
          <ul className="flex flex-col gap-1 mt-1">
            {character.items.map((item) => (
              <li key={item.item_id}>
                <label className="flex items-center gap-2 text-xs cursor-pointer hover:bg-muted/30 p-1 rounded">
                  <Checkbox
                    checked={item.carried}
                    onCheckedChange={(checked) =>
                      onOperate({
                        name: 'set_item_carried',
                        args: {
                          item_id: item.item_id,
                          carried: checked === true,
                          character_id: characterId,
                        },
                      })
                    }
                  />
                  <span className={item.carried ? 'font-medium text-foreground' : 'text-muted-foreground'}>
                    {item.item_id}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No items on the sheet yet.</p>
        )}
      </div>

      {/* Contacts */}
      {(character.friend || character.rival) && (
        <div className="flex flex-col gap-1 text-xs rounded-md border border-border/40 p-2.5 bg-background/40">
          <span className="font-semibold text-muted-foreground uppercase tracking-wider">Contacts</span>
          {character.friend && (
            <div>
              <strong className="text-emerald-500 font-medium">Friend:</strong> {character.friend}
            </div>
          )}
          {character.rival && (
            <div>
              <strong className="text-rose-500 font-medium">Rival:</strong> {character.rival}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
