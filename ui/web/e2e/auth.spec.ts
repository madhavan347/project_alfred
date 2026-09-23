/**
 * Access control: the UI can type into agent sessions, so it demands its token, rejects foreign
 * hosts and origins, and refuses unauthenticated WebSockets.
 */
import { request as httpRequest } from 'node:http'
import { expect, test } from '@playwright/test'
import { env } from './helpers'

function raw(path: string, headers: Record<string, string>): Promise<number> {
  const url = new URL(env.base)
  return new Promise((resolve, reject) => {
    const request = httpRequest({ host: url.hostname, port: url.port, path, headers }, (response) => {
      response.resume()
      resolve(response.statusCode ?? 0)
    })
    request.on('error', reject)
    request.end()
  })
}

test('a browser without the token is asked to sign in, and a wrong token is refused', async ({ page }) => {
  await page.goto(env.base)
  await expect(page.getByRole('heading', { name: 'Sign in to Alfred' })).toBeVisible()
  await page.getByLabel('Access token').fill('not-the-token')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText('That access token is not valid')
  await page.getByLabel('Access token').fill(env.token)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.locator('.shell')).toBeVisible()
  await expect(page.locator('.topbar')).toContainText('Live')
})

test('a link with a wrong token says so', async ({ page }) => {
  await page.goto(`${env.base}/?token=wrong`)
  await expect(page).toHaveURL(/signin=invalid/)
  await expect(page.getByText('The token in that link was not accepted.')).toBeVisible()
})

test('the API rejects missing tokens, foreign hosts, and cross-site origins', async () => {
  const url = new URL(env.base)
  expect(await raw('/api/snapshot', { Host: url.host })).toBe(401)
  expect(await raw('/api/snapshot', { Host: url.host, 'X-Alfred-Token': env.token })).toBe(200)
  expect(await raw('/api/snapshot', { Host: 'attacker.example', 'X-Alfred-Token': env.token })).toBe(403)
  expect(await raw('/api/health', { Host: url.host })).toBe(200)
  const crossSite = await fetch(`${env.base}/api/runs/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Alfred-Token': env.token, Origin: 'http://evil.example' },
    body: JSON.stringify({ tasks: [1] }),
  })
  expect(crossSite.status).toBe(403)
})

test('WebSockets need the token too', async () => {
  const socketBase = env.base.replace('http', 'ws')
  const refused = await new Promise<string>((resolve) => {
    const socket = new WebSocket(`${socketBase}/api/live`)
    socket.onopen = () => resolve('open')
    socket.onerror = () => resolve('refused')
  })
  expect(refused).toBe('refused')
  const accepted = await new Promise<string>((resolve) => {
    const socket = new WebSocket(`${socketBase}/api/live?token=${env.token}`)
    socket.onmessage = (event) => {
      resolve(JSON.parse(String(event.data)).type)
      socket.close()
    }
    socket.onerror = () => resolve('refused')
  })
  expect(accepted).toBe('snapshot')
})
