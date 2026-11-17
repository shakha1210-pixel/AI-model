import { Outlet, createFileRoute } from '@tanstack/react-router'
import { SharedAppLayout } from '@/layouts/shared-app-layout'

/**
 * App shell layout — mounted at the REAL `/app` segment (not a pathless `_app`).
 *
 * Everything under `src/routes/app/` renders inside this sidebar chrome:
 *   src/routes/app/index.tsx     → /app          (the dashboard home)
 *   src/routes/app/settings.tsx  → /app/settings (add pages like this)
 *
 * WHY A NAMED SEGMENT, NOT `_app`: a `_`-prefixed layout is PATHLESS — it adds no
 * URL segment, so `_app/index.tsx` IS the `/` route and collides with the root
 * `src/routes/index.tsx` (and a childless `_app.tsx` collides the same way). The
 * build then fails with "Conflicting configuration paths … '/', '/'". Under `/app`
 * that collision is impossible: `app/index.tsx` can only ever be `/app`.
 *
 * DASHBOARD-ONLY PRODUCT (no landing page)? Keep this shell and make the root
 * redirect to it — `src/routes/index.tsx` → `beforeLoad: () => { throw redirect({ to: '/app' }) }`.
 * Redirect to `/app` (a real path), never to a pathless route.
 *
 * LANDING / MARKETING / CONTENT / GAME? You don't need this shell: delete
 * `src/routes/app.tsx` and the `src/routes/app/` folder. Deleting is always safe.
 *
 * Auth-gate the whole shell by wrapping <Outlet /> in your auth check here — one
 * place, not per page. Browser-only state (blink.auth, localStorage, window) must
 * sit inside <BlinkClientBoundary> (wrap the whole shell if the entire app is
 * browser-only). Do NOT use the route's `ssr: false` — a client-only route in this
 * TanStack Start template hits Start's server-context `node:async_hooks` path (a
 * throwing browser stub) and ships a BLANK preview ("AsyncLocalStorage is not a
 * constructor").
 */
export const Route = createFileRoute('/app')({
  component: AppLayout,
})

function AppLayout() {
  return (
    <SharedAppLayout appName="App">
      <Outlet />
    </SharedAppLayout>
  )
}
