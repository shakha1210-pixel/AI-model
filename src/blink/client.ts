import { createClient } from '@blinkdotnew/sdk'

export const blink = createClient({
  projectId: import.meta.env.VITE_BLINK_PROJECT_ID || 'dilshodbek-portfolio-82nhtvqh',
  publishableKey: import.meta.env.VITE_BLINK_PUBLISHABLE_KEY || 'blnk_pk_n_zHl4IvYbj99B-6A0Rbu2a-cooqL5_7',
  authRequired: false,
  auth: { mode: 'managed' },
})
