import { useState } from 'react'

import Markdown from 'react-markdown'

import { apiClient } from '@/api/client'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'
import { BookOpenText } from 'lucide-react'

// C1: "the required attribution text ... must appear in any distributed UI's
// credits" - fetched from the server's /api/notice (NOTICE.md itself, so
// there's nothing to keep in sync by hand) and rendered on demand, not
// unconditionally, since it's licensing reading material, not game content.
export function CreditsDialog() {
  const [text, setText] = useState<string | null>(null)

  async function loadNotice() {
    if (text !== null) return
    const { data } = await apiClient.GET('/api/notice')
    if (data) setText(data.text)
  }

  return (
    <Dialog onOpenChange={(open) => open && loadNotice()}>
      <SidebarMenuItem>
        <DialogTrigger asChild>
          <SidebarMenuButton tooltip="Credits & licensing">
            <BookOpenText className="opacity-80" />
            <span>Credits & licensing</span>
          </SidebarMenuButton>
        </DialogTrigger>
      </SidebarMenuItem>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Credits & licensing</DialogTitle>
        </DialogHeader>
        <div className="text-sm [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mb-1 [&_h2]:mt-4 [&_h2]:text-sm [&_h2]:font-semibold [&_p]:mb-3 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_a]:underline">
          {text ? <Markdown>{text}</Markdown> : <p className="text-muted-foreground">Loading…</p>}
        </div>
      </DialogContent>
    </Dialog>
  )
}
