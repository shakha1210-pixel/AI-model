import { createFileRoute } from '@tanstack/react-router'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * Dashboard home — `/app` (this file is the index of the `/app` segment, so its
 * path is `/app`, NOT `/app/index`). Rendered inside the sidebar shell defined in
 * `src/routes/app.tsx`.
 *
 * Add sibling pages as files in this folder: `src/routes/app/orders.tsx` → /app/orders.
 * Every page you add must also get a matching sidebar link (see AppSidebarShell),
 * and every sidebar link must have a real page — never ship a nav link to a 404.
 *
 * Replace this placeholder body with the real dashboard.
 */
export const Route = createFileRoute('/app/')({
  head: () => ({
    meta: [
      { title: 'Dashboard · Blink App' },
      { name: 'description', content: 'Your app dashboard.' },
    ],
  }),
  component: DashboardHome,
})

function DashboardHome() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Replace this with your real dashboard. Add pages under{' '}
          <code className="rounded bg-muted px-1">src/routes/app/</code>.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {['Overview', 'Activity', 'Getting started'].map(title => (
          <Card key={title}>
            <CardHeader>
              <CardTitle className="text-sm font-medium">{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Placeholder card — swap in real data.</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
