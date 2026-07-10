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
import { ScrollText, Dice5, User, Swords, MessageSquare } from "lucide-react"

// Core navigation items
const items = [
  {
    title: "Campaign",
    url: "/",
    icon: Swords,
  },
  {
    title: "Play",
    url: "/play",
    icon: MessageSquare,
  },
  {
    title: "Character Sheet",
    url: "/sheet",
    icon: User,
  },
  {
    title: "Journal",
    url: "/journal",
    icon: ScrollText,
  },
]

export function AppSidebar() {
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
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    {/* Active state is handled by Tanstack Router via activeProps */}
                    <Link to={item.url} activeProps={{ className: "bg-accent/50 text-accent-foreground font-medium" }}>
                      <item.icon className="opacity-80" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
