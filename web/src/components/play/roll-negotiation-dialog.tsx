import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { CharacterSnapshot, RollDecision, RollProposal } from '@/hooks/use-session-socket'

const POSITIONS = ['controlled', 'risky', 'desperate'] as const
const EFFECTS = ['zero', 'limited', 'standard', 'great', 'extreme'] as const

type Trade = 'none' | 'worse_position_better_effect' | 'better_position_worse_effect'

function stepPosition(position: RollProposal['position'], delta: number) {
  const index = POSITIONS.indexOf(position)
  return POSITIONS[Math.max(0, Math.min(POSITIONS.length - 1, index + delta))]
}

function stepEffect(effect: RollProposal['effect'], delta: number) {
  const index = EFFECTS.indexOf(effect)
  return EFFECTS[Math.max(0, Math.min(EFFECTS.length - 1, index + delta))]
}

// FR-16: shown whenever the GM agent proposes an action roll (position and
// effect - Action Roll steps 1-4). The player negotiates bonus dice and any
// trade-off (step 5, "Add Bonus Dice"/"Trading Position for Effect") before
// the roll actually executes. Also offers SRD "Teamwork"/"Assist": any other
// PC in the session (solo play's one seat may control several, FR-25) can
// take 1 stress to give the roller +1d.
export function RollNegotiationDialog({
  proposal,
  characters,
  onDecide,
}: {
  proposal: RollProposal
  characters: Record<string, CharacterSnapshot>
  onDecide: (decision: RollDecision) => void
}) {
  const [pushDice, setPushDice] = useState(false)
  const [pushEffect, setPushEffect] = useState(false)
  const [devilsBargainAccepted, setDevilsBargainAccepted] = useState(false)
  const [devilsBargainText, setDevilsBargainText] = useState('')
  const [trade, setTrade] = useState<Trade>('none')
  const [assistCharacterId, setAssistCharacterId] = useState<string>('none')

  const assistCandidates = Object.entries(characters).filter(
    ([characterId]) => characterId !== proposal.character_id,
  )

  let position = proposal.position
  let effect = proposal.effect
  if (trade === 'worse_position_better_effect') {
    position = stepPosition(position, 1)
    effect = stepEffect(effect, 1)
  } else if (trade === 'better_position_worse_effect') {
    position = stepPosition(position, -1)
    effect = stepEffect(effect, -1)
  }
  if (pushEffect) effect = stepEffect(effect, 1)
  const assisted = assistCharacterId !== 'none'
  const bonusDice = (pushDice ? 1 : 0) + (devilsBargainAccepted ? 1 : 0) + (assisted ? 1 : 0)
  const stressCost = (pushDice ? 2 : 0) + (pushEffect ? 2 : 0)

  function handleSubmit() {
    onDecide({
      push_dice: pushDice,
      push_effect: pushEffect,
      devils_bargain: devilsBargainAccepted
        ? devilsBargainText.trim() || "Devil's Bargain accepted"
        : null,
      trade: trade === 'none' ? null : trade,
      assist_character_id: assisted ? assistCharacterId : null,
    })
  }

  return (
    <Dialog open modal>
      <DialogContent showCloseButton={false} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="capitalize">{proposal.action}</DialogTitle>
          <DialogDescription>
            {proposal.pool_size}d pool &middot; <span className="capitalize">{position}</span>{' '}
            position &middot; <span className="capitalize">{effect}</span> effect
            {bonusDice > 0 && ` (+${bonusDice}d)`}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-muted-foreground">
              Trade position for effect
            </span>
            <RadioGroup value={trade} onValueChange={(value) => setTrade(value as Trade)}>
              <label className="flex items-center gap-2 text-sm">
                <RadioGroupItem value="none" /> Accept as proposed
              </label>
              <label className="flex items-center gap-2 text-sm">
                <RadioGroupItem value="worse_position_better_effect" /> Push my luck: worse
                position, better effect
              </label>
              <label className="flex items-center gap-2 text-sm">
                <RadioGroupItem value="better_position_worse_effect" /> Play it safe: better
                position, worse effect
              </label>
            </RadioGroup>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-muted-foreground">Bonus dice</span>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={pushDice}
                onCheckedChange={(checked) => {
                  setPushDice(checked === true)
                  if (checked) setDevilsBargainAccepted(false)
                }}
              />
              Push yourself for +1d (2 stress)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={pushEffect}
                onCheckedChange={(checked) => setPushEffect(checked === true)}
              />
              Push yourself for +1 effect (2 stress)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={devilsBargainAccepted}
                onCheckedChange={(checked) => {
                  setDevilsBargainAccepted(checked === true)
                  if (checked) setPushDice(false)
                }}
              />
              Accept a Devil's Bargain for +1d (free)
            </label>
            {devilsBargainAccepted && (
              <div className="flex flex-col gap-1 pl-6">
                <Label htmlFor="devils-bargain-text" className="text-xs text-muted-foreground">
                  What's the price?
                </Label>
                <Input
                  id="devils-bargain-text"
                  value={devilsBargainText}
                  onChange={(event) => setDevilsBargainText(event.target.value)}
                  placeholder="e.g. tick the Heat clock"
                />
              </div>
            )}
          </div>

          {assistCandidates.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-muted-foreground">
                Teamwork: assist
              </span>
              <RadioGroup value={assistCharacterId} onValueChange={setAssistCharacterId}>
                <label className="flex items-center gap-2 text-sm">
                  <RadioGroupItem value="none" /> No one assists
                </label>
                {assistCandidates.map(([characterId, character]) => (
                  <label key={characterId} className="flex items-center gap-2 text-sm">
                    <RadioGroupItem value={characterId} /> {character.name} assists (they take 1
                    stress, +1d to this roll)
                  </label>
                ))}
              </RadioGroup>
            </div>
          )}

          {stressCost > 0 && (
            <p className="text-xs text-muted-foreground">Costs {stressCost} stress.</p>
          )}
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit}>Roll the dice</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
