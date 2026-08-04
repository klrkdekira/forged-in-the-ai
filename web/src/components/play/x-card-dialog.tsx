import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

export function XCardDialog({
  open,
  onOpenChange,
  onInvoke,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onInvoke: (note?: string, text?: string) => void
}) {
  const [note, setNote] = useState('')
  const [text, setText] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    onInvoke(note.trim() || undefined, text.trim() || undefined)
    setNote('')
    setText('')
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-destructive">Invoke X-Card (Safety Tool)</DialogTitle>
          <DialogDescription>
            The X-Card allows anyone at the table to pause, edit out, or redirect content without argument.
            The GM will immediately adjust the fiction.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5 text-xs">
            <label htmlFor="x-card-note" className="font-semibold text-foreground">
              Flagged Subject / Topic (Optional)
            </label>
            <Input
              id="x-card-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Animal cruelty, Graphic harm..."
            />
          </div>

          <div className="flex flex-col gap-1.5 text-xs">
            <label htmlFor="x-card-text" className="font-semibold text-foreground">
              Redirection Guidance for the GM (Optional)
            </label>
            <Input
              id="x-card-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="e.g. Fade to black and move to the rooftop escape..."
            />
          </div>

          <DialogFooter className="mt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive">
              Invoke X-Card
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
