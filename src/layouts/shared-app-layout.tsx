/**
 * SaaS app chrome (sidebar + main) — OPT-IN, not the default.
 * The template root (__root.tsx) is full-bleed by default. This is already wired
 * up for you by `src/routes/app.tsx` (the `/app` segment); add dashboard pages as
 * files under `src/routes/app/`. Never mount it from a pathless `src/routes/_app.tsx`
 * — a `_`-prefixed layout adds no URL segment, so it (or its `index.tsx`) claims "/"
 * and collides with the root index route, failing the build. Do not wrap individual
 * pages in Shell or duplicate sidebars/top bars. Landing/marketing/content apps
 * don't need this at all — delete `src/routes/app.tsx` + `src/routes/app/`.
 */
import React, { createContext, useContext } from 'react'
import { Shell } from '../Shell'
import { AppSidebarShell } from '../components/AppSidebarShell'

export type SharedLayoutContextValue = {
  appName: string
}

const SharedLayoutContext = createContext<SharedLayoutContextValue | null>(null)

/** Use inside routes/pages that need app name or layout metadata — never for duplicating Shell. */
export function useSharedLayout(): SharedLayoutContextValue {
  const ctx = useContext(SharedLayoutContext)
  if (!ctx) {
    throw new Error('useSharedLayout must be used within SharedAppLayout')
  }
  return ctx
}

export type SharedAppLayoutProps = {
  appName?: string
  /** Override default sidebar; keep same flex structure as AppSidebarShell */
  sidebar?: React.ReactNode
  children: React.ReactNode
}

export function SharedAppLayout({
  appName = 'App',
  sidebar = <AppSidebarShell />,
  children,
}: SharedAppLayoutProps) {
  const value = React.useMemo(() => ({ appName }), [appName])

  return (
    <SharedLayoutContext.Provider value={value}>
      <div className="flex min-h-dvh w-full flex-1 flex-col">
        <Shell appName={appName} sidebar={sidebar}>
          {children}
        </Shell>
      </div>
    </SharedLayoutContext.Provider>
  )
}
