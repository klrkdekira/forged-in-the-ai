import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { AlertTriangle, CheckCircle2, Dices, RotateCcw, ShieldAlert, Sparkles, Trophy } from 'lucide-react'

export interface DiceRollResult {
  dice: number[]
  highest: number
  band: 'critical' | 'success' | 'partial' | 'failure' | string
  action?: string
  position?: string
  effect?: string
}

interface AnimatedDiceRollerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  result?: DiceRollResult
  poolSize?: number
  actionName?: string
  position?: string
  effect?: string
  onComplete?: () => void
}

// 3D rotation mappings for D6 faces to face top
const ROTATIONS: Record<number, { x: number; y: number }> = {
  1: { x: 0, y: 0 },
  6: { x: 180, y: 0 },
  2: { x: -90, y: 0 },
  5: { x: 90, y: 0 },
  3: { x: 0, y: -90 },
  4: { x: 0, y: 90 },
}

export function AnimatedDiceRoller({
  open,
  onOpenChange,
  result: initialResult,
  poolSize = 2,
  actionName = 'Action Roll',
  position,
  effect,
  onComplete,
}: AnimatedDiceRollerProps) {
  const [rolling, setRolling] = useState(true)
  const [currentResult, setCurrentResult] = useState<DiceRollResult | null>(null)
  const [rotations, setRotations] = useState<Array<{ x: number; y: number; z: number }>>([])

  function generateRoll(size: number): DiceRollResult {
    const dice: number[] = []
    const count = Math.max(1, size)
    for (let i = 0; i < count; i++) {
      dice.push(Math.floor(Math.random() * 6) + 1)
    }
    // Zero pool / 1d fallback rule if pool is 0: roll 2d, pick lowest
    const sorted = [...dice].sort((a, b) => b - a)
    const highest = sorted[0]
    const sixes = dice.filter((d) => d === 6).length

    let band: 'critical' | 'success' | 'partial' | 'failure' = 'failure'
    if (sixes >= 2) {
      band = 'critical'
    } else if (highest === 6) {
      band = 'success'
    } else if (highest === 4 || highest === 5) {
      band = 'partial'
    } else {
      band = 'failure'
    }

    return {
      dice,
      highest,
      band,
      action: actionName,
      position,
      effect,
    }
  }

  function startRollAnimation(rollRes: DiceRollResult) {
    setRolling(true)
    // Initial random tumble rotations
    const initialRot = rollRes.dice.map(() => ({
      x: Math.floor(Math.random() * 360) + 720,
      y: Math.floor(Math.random() * 360) + 720,
      z: Math.floor(Math.random() * 360) + 360,
    }))
    setRotations(initialRot)

    setTimeout(() => {
      // Final target rotations based on actual values
      const finalRot = rollRes.dice.map((val) => {
        const base = ROTATIONS[val] || { x: 0, y: 0 }
        return {
          x: base.x + 1440, // 4 full turns
          y: base.y + 1440,
          z: 0,
        }
      })
      setRotations(finalRot)
      setRolling(false)
      if (onComplete) onComplete()
    }, 1200)
  }

  useEffect(() => {
    if (open) {
      const res = initialResult || generateRoll(poolSize)
      setCurrentResult(res)
      startRollAnimation(res)
    }
  }, [open, initialResult, poolSize])

  function handleReroll() {
    const res = generateRoll(poolSize)
    setCurrentResult(res)
    startRollAnimation(res)
  }

  if (!open || !currentResult) return null

  const band = currentResult.band
  const isCritical = band === 'critical'
  const isSuccess = band === 'success'
  const isPartial = band === 'partial'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg border-border/80 bg-background/95 backdrop-blur-xl shadow-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl capitalize">
            <Dices className="size-6 text-primary animate-spin" />
            {currentResult.action || 'Action Roll'}
          </DialogTitle>
          <DialogDescription>
            {currentResult.dice.length}d Pool
            {currentResult.position && ` · Position: ${currentResult.position}`}
            {currentResult.effect && ` · Effect: ${currentResult.effect}`}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center justify-center py-6 gap-6 min-h-[220px] overflow-hidden">
          {/* 3D Dice Tray Area */}
          <div
            className="flex flex-wrap items-center justify-center gap-6 p-6 rounded-2xl bg-gradient-to-b from-muted/30 to-muted/10 border border-border/40 w-full min-h-[140px] relative overflow-hidden"
            style={{ perspective: '1000px' }}
          >
            {currentResult.dice.map((val, idx) => {
              const rot = rotations[idx] || { x: 0, y: 0, z: 0 }
              const isHighest = val === currentResult.highest
              return (
                <div
                  key={idx}
                  className="relative transition-transform duration-1000 ease-out"
                  style={{
                    transformStyle: 'preserve-3d',
                    transform: `rotateX(${rot.x}deg) rotateY(${rot.y}deg) rotateZ(${rot.z}deg)`,
                    width: '64px',
                    height: '64px',
                  }}
                >
                  <DieCube value={val} isHighest={isHighest && !rolling} />
                </div>
              )
            })}
          </div>

          {/* Outcome Announcement */}
          {!rolling && (
            <div
              className={`flex flex-col items-center gap-1.5 p-4 rounded-xl border w-full text-center animate-in fade-in zoom-in-95 duration-300 ${
                isCritical
                  ? 'bg-amber-500/10 border-amber-500/40 text-amber-500 shadow-lg shadow-amber-500/10'
                  : isSuccess
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-500 shadow-lg shadow-emerald-500/10'
                  : isPartial
                  ? 'bg-amber-500/10 border-amber-500/40 text-amber-500 shadow-lg shadow-amber-500/10'
                  : 'bg-rose-500/10 border-rose-500/40 text-rose-500 shadow-lg shadow-rose-500/10'
              }`}
            >
              <div className="flex items-center gap-2 text-base font-bold tracking-wide uppercase">
                {isCritical && <Trophy className="size-5 animate-bounce text-amber-400" />}
                {isSuccess && <CheckCircle2 className="size-5 text-emerald-400" />}
                {isPartial && <AlertTriangle className="size-5 text-amber-400" />}
                {!isCritical && !isSuccess && !isPartial && (
                  <ShieldAlert className="size-5 text-rose-400" />
                )}
                {isCritical
                  ? 'Critical Success!'
                  : isSuccess
                  ? 'Full Success'
                  : isPartial
                  ? 'Partial Success'
                  : 'Failure / Bad Consequence'}
              </div>
              <p className="text-xs opacity-90 font-medium">
                Highest Die: <strong className="text-sm font-extrabold">{currentResult.highest}</strong>
                {isCritical && ' (Double 6s!)'}
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="flex items-center justify-between sm:justify-between">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleReroll}
            disabled={rolling}
            className="flex items-center gap-1.5 text-xs"
          >
            <RotateCcw className="size-3.5" /> Re-roll
          </Button>
          <Button type="button" size="sm" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DieCube({ value, isHighest }: { value: number; isHighest: boolean }) {
  const borderStyle = isHighest
    ? 'border-2 border-amber-400 shadow-lg shadow-amber-500/30'
    : 'border border-border/60 shadow-md'

  return (
    <div className="relative w-full h-full" style={{ transformStyle: 'preserve-3d' }}>
      {/* Front: 1 */}
      <div
        className={`absolute inset-0 rounded-xl bg-card flex items-center justify-center ${borderStyle}`}
        style={{ transform: 'translateZ(32px)' }}
      >
        <PipPattern count={1} />
      </div>
      {/* Back: 6 */}
      <div
        className={`absolute inset-0 rounded-xl bg-card flex items-center justify-center ${borderStyle}`}
        style={{ transform: 'rotateY(180deg) translateZ(32px)' }}
      >
        <PipPattern count={6} />
      </div>
      {/* Top: 2 */}
      <div
        className={`absolute inset-0 rounded-xl bg-card flex items-center justify-center ${borderStyle}`}
        style={{ transform: 'rotateX(90deg) translateZ(32px)' }}
      >
        <PipPattern count={2} />
      </div>
      {/* Bottom: 5 */}
      <div
        className={`absolute inset-0 rounded-xl bg-card flex items-center justify-center ${borderStyle}`}
        style={{ transform: 'rotateX(-90deg) translateZ(32px)' }}
      >
        <PipPattern count={5} />
      </div>
      {/* Right: 3 */}
      <div
        className={`absolute inset-0 rounded-xl bg-card flex items-center justify-center ${borderStyle}`}
        style={{ transform: 'rotateY(90deg) translateZ(32px)' }}
      >
        <PipPattern count={3} />
      </div>
      {/* Left: 4 */}
      <div
        className={`absolute inset-0 rounded-xl bg-card flex items-center justify-center ${borderStyle}`}
        style={{ transform: 'rotateY(-90deg) translateZ(32px)' }}
      >
        <PipPattern count={4} />
      </div>
    </div>
  )
}

function PipPattern({ count }: { count: number }) {
  const pipClass = 'size-2.5 rounded-full bg-foreground shadow-xs'
  if (count === 1) {
    return <div className={pipClass} />
  }
  if (count === 2) {
    return (
      <div className="grid grid-cols-2 gap-4 p-2 w-full h-full justify-items-center items-center">
        <div className={pipClass} />
        <div className={`${pipClass} col-start-2 row-start-2`} />
      </div>
    )
  }
  if (count === 3) {
    return (
      <div className="grid grid-cols-3 gap-2 p-2 w-full h-full justify-items-center items-center">
        <div className={pipClass} />
        <div className={`${pipClass} col-start-2 row-start-2`} />
        <div className={`${pipClass} col-start-3 row-start-3`} />
      </div>
    )
  }
  if (count === 4) {
    return (
      <div className="grid grid-cols-2 gap-3 p-2 w-full h-full justify-between items-between">
        <div className={pipClass} />
        <div className={pipClass} />
        <div className={pipClass} />
        <div className={pipClass} />
      </div>
    )
  }
  if (count === 5) {
    return (
      <div className="relative w-full h-full p-2.5 flex flex-col justify-between">
        <div className="flex justify-between">
          <div className={pipClass} />
          <div className={pipClass} />
        </div>
        <div className="flex justify-center">
          <div className={pipClass} />
        </div>
        <div className="flex justify-between">
          <div className={pipClass} />
          <div className={pipClass} />
        </div>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-2 gap-2 p-2 w-full h-full justify-items-center items-center">
      <div className={pipClass} />
      <div className={pipClass} />
      <div className={pipClass} />
      <div className={pipClass} />
      <div className={pipClass} />
      <div className={pipClass} />
    </div>
  )
}
