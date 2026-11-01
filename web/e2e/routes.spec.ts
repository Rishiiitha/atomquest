import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const routes = ['/twin', '/why', '/app', '/fleet', '/evidence', '/hardware', '/about', '/demo']
const screenshots = resolve(process.cwd(), '../docs/screenshots')

test.beforeEach(async ({ page }) => {
  await page.route('http://127.0.0.1:8000/**', (route) =>
    route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }),
  )
})

test('all routes render in Demo-Safe mode on desktop and phone', async ({ page }) => {
  test.setTimeout(120_000)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    const text = message.text()
    // The 503 is an intentional test stub that exercises Demo-Safe fallback behavior.
    if (message.type() === 'error' && !text.includes('503 (Service Unavailable)')) consoleErrors.push(text)
  })
  await mkdir(screenshots, { recursive: true })

  for (const [index, route] of routes.entries()) {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.goto(route)
    await expect(page.locator('main')).toBeVisible()
    if (route === '/twin') {
      await expect(page.getByText('Data unavailable. Run the local pipeline to create evidence.')).toHaveCount(0)
      await expect(page.getByRole('img', { name: 'Two-dimensional purifier flow schematic' })).toBeVisible()
    }
    await expect(page.getByText('Demo-Safe').first()).toBeVisible()
    expect((await page.locator('main').innerText()).length).toBeGreaterThan(20)
    await page.screenshot({ path: resolve(screenshots, `${index + 1}-${route.slice(1)}-desktop.png`), fullPage: true })

    await page.setViewportSize({ width: 360, height: 800 })
    await page.reload()
    await expect(page.locator('main')).toBeVisible()
    if (route === '/twin') {
      await expect(page.getByText('Data unavailable. Run the local pipeline to create evidence.')).toHaveCount(0)
      await expect(page.getByRole('img', { name: 'Two-dimensional purifier flow schematic' })).toBeVisible()
    }
    await page.screenshot({ path: resolve(screenshots, `${index + 1}-${route.slice(1)}-phone.png`), fullPage: true })
  }

  expect(consoleErrors).toEqual([])
})

test('the physics explainer loads its generated golden artifact', async ({ page }) => {
  await page.goto('/why')
  await expect(page.getByText('Golden example G1')).toBeVisible()
  await expect(page.getByText('Healthy membrane · higher TDS')).toBeVisible()
})

test('offline event injection uses a generated replay bundle', async ({ page }) => {
  await page.goto('/twin')
  await page.getByRole('button', { name: /silt spike/i }).click()
  await expect(page.getByRole('status')).toContainText('Event-adjusted forecast loaded')
})

test('WebGL scene renders or falls back cleanly after context loss', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().includes('503 (Service Unavailable)')) errors.push(message.text())
  })
  await page.goto('/twin')
  const canvas = page.locator('.three-stage canvas')
  const schematic = page.getByRole('img', { name: 'Two-dimensional purifier flow schematic' })
  await expect(canvas.or(schematic)).toBeVisible()
  await page.waitForTimeout(500)
  if (await canvas.isVisible().catch(() => false)) {
    const liveWebgl = await canvas.evaluate((element: HTMLCanvasElement) => {
      const context = element.getContext('webgl2')
      return Boolean(context && !context.isContextLost())
    }).catch(() => false)
    if (!liveWebgl) await expect(schematic).toBeVisible()
  } else {
    await expect(schematic).toBeVisible()
  }
  await page.screenshot({ path: resolve(screenshots, 'twin-webgl.png'), fullPage: true })
  expect(errors).toEqual([])
})
