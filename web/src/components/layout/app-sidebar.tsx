import { Link } from "@tanstack/react-router"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { PlayLink } from "@/components/play-link"
import { useLastCampaignId } from "@/hooks/use-last-campaign-id"
import { ScrollText, Dice5, User, Swords, MessageSquare } from "lucide-react"

const activeProps = { className: "bg-accent/50 text-accent-foreground font-medium" }

export function AppSidebar() {
  // FR-18: /play now needs a campaignId - "Play" goes to the last campaign
  // opened, or the picker (/) if none is known yet.
  const lastCampaignId = useLastCampaignId()

  return (
    <Sidebar collapsible="icon" className="border-r border-border/50 bg-background/50 backdrop-blur-md">
      <SidebarHeader className="py-4">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="hover:bg-transparent">
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                <Dice5 className="size-5" />
              </div>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-bold text-lg tracking-tight">Forged AI</span>
                <span className="text-xs text-muted-foreground font-medium">Rules Engine</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
            Game View
          </SidebarGroupLabel>
          <SidebarGroupContent>
            {/* Active state is handled by Tanstack Router via activeProps.
                Written out explicitly rather than mapped over a data array:
                "Play" targets a different route shape (last-opened campaign
                vs. these fixed routes), so a shared item shape doesn't fit. */}
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Campaign">
                  <Link to="/" activeProps={activeProps}>
                    <Swords className="opacity-80" />
                    <span>Campaign</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Play">
                  <PlayLink campaignId={lastCampaignId}>
                    <MessageSquare className="opacity-80" />
                    <span>Play</span>
                  </PlayLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Character Sheet">
                  <Link to="/sheet" activeProps={activeProps}>
                    <User className="opacity-80" />
                    <span>Character Sheet</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Journal">
                  <Link to="/journal" activeProps={activeProps}>
                    <ScrollText className="opacity-80" />
                    <span>Journal</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
