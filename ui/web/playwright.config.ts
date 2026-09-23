import { defineConfig } from '@playwright/test'

// End-to-end tests drive the real UI against a real alfred-ui server, real tmux sessions, real
// Git repositories with a bare remote, and a scripted agent that calls the real alfred CLI.
export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  globalSetup: './e2e/global-setup.ts',
  outputDir: './test-results',
  use: {
    viewport: { width: 1480, height: 940 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 20_000,
  },
})
