import * as React from "react"
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "./app-sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />
        <main className="flex min-h-svh flex-1 flex-col relative bg-background/95">
          {/* Frosted glass topbar */}
          <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b border-border/40 bg-background/60 px-6 backdrop-blur-md">
            <SidebarTrigger className="hover:bg-accent/50 transition-colors" />
            <div className="flex-1" />
            <div className="flex items-center gap-4">
              {/* Placeholder for user profile / session status */}
              <div className="size-8 rounded-full bg-accent/50 border border-accent/30" />
            </div>
          </header>
          {/* Main content container */}
          <div className="flex-1 p-6 md:p-8 overflow-auto max-w-7xl mx-auto w-full">
            {children}
          </div>
        </main>
      </SidebarProvider>
    </TooltipProvider>
  )
}
