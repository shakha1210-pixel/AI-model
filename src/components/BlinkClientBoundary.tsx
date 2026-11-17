import { ClientOnly } from '@tanstack/react-router'
import type { ReactNode } from 'react'

/**
 * SSR-safe boundary. Every route in this template is SERVER-RENDERED / prerendered
 * (TanStack Start). Anything that touches the browser AT RENDER TIME — Blink SDK
 * auth state (`blink.auth`, `onAuthStateChanged`), `localStorage`/`window`, or a
 * hook that reads them — throws or hydration-mismatches on the server and ships a
 * blank/broken first page. Wrap that subtree here: the server renders `fallback`,
 * and the real UI mounts in the browser. Keep static/marketing content OUTSIDE the
 * boundary so it stays server-rendered and crawlable.
 *
 *   <BlinkClientBoundary fallback={<Skeleton />}>
 *     <AuthedDashboard />   // reads blink.auth — browser only
 *   </BlinkClientBoundary>
 *
 * If the WHOLE page needs the browser, wrap its entire tree in this boundary.
 * Do NOT use the route's `ssr: false` option: a client-only route in this TanStack
 * Start template hits Start's server-context `node:async_hooks` path (externalized
 * to a throwing stub in the browser) and ships a BLANK preview ("AsyncLocalStorage
 * is not a constructor"). This boundary (TanStack's `ClientOnly`) is the supported
 * client-only escape hatch, and keeps the shell server-rendered (better for SEO).
 */
export function BlinkClientBoundary({
  children,
  fallback = null,
}: {
  children: ReactNode
  fallback?: ReactNode
}) {
  return <ClientOnly fallback={fallback}>{children}</ClientOnly>
}
