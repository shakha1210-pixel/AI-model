/**
 * Shell — Mobile-responsive app layout (shadcn/ui based).
 *
 * USAGE (in a route or SharedAppLayout):
 *   <Shell sidebar={<MySidebarContent />}>
 *     <Page>...</Page>
 *   </Shell>
 *
 * Desktop (md+): the sidebar is a fixed column on the left, main content fills
 * the rest. Mobile: the sidebar is hidden and opens in a Sheet drawer via the
 * hamburger button in the mobile header. Customize freely — this is your code.
 */
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent } from '@/components/ui/sheet'

interface ShellProps {
  /** Sidebar content — e.g. <AppSidebarShell /> or your own nav */
  sidebar: ReactNode
  /** App name shown in the mobile header */
  appName?: string
  children: ReactNode
}

export function Shell({ sidebar, appName = 'App', children }: ShellProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex min-h-dvh">
      {/* Desktop sidebar — hidden on mobile, always visible on md+.
          AppSidebarShell owns its own width and collapse animation. */}
      <aside className="hidden md:block shrink-0">{sidebar}</aside>

      {/* Mobile sidebar — Sheet drawer opened by the hamburger below. */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-64 p-0">
          {sidebar}
        </SheetContent>
      </Sheet>

      {/* Main content column */}
      <main className="flex flex-1 min-w-0 flex-col">
        {/* Mobile header — hamburger + app name, only shown below md. */}
        <div className="md:hidden flex items-center gap-3 px-4 h-14 border-b border-border bg-background sticky top-0 z-30">
          <Button
            variant="ghost"
            size="icon"
            className="-ml-2"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
          >
            <Menu className="size-5" />
          </Button>
          <span className="font-semibold text-sm">{appName}</span>
        </div>

        {children}
      </main>
    </div>
  )
}
