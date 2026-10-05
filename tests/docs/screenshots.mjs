#!/usr/bin/env node
/**
 * Regenerates docs/images from a freshly set-up demo whose translator talks to stand-in.mjs.
 * See docs/DEVELOPER.md -> Docs screenshots.
 *
 *   BASE_URL (default http://127.0.0.1:8093)
 *   DEMO_ADMIN_EMAIL / DEMO_ADMIN_PASSWORD     settings screens (superuser)
 *   DEMO_EDITOR_EMAIL / DEMO_EDITOR_PASSWORD   translating (Moderators group)
 */
import { chromium } from 'playwright'

const B = process.env.BASE_URL || 'http://127.0.0.1:8093'
const OUT = new URL('../../docs/images', import.meta.url).pathname
const LIVE_API = 'https://api.supertext.com/v1/'
const pad = (r, p = 8) => ({ x: Math.max(0, r.x - p), y: Math.max(0, r.y - p), width: r.width + 2 * p, height: r.height + 2 * p })

const browser = await chromium.launch()

async function session(email, password) {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 860 } })).newPage()
  await page.goto(`${B}/admin/login/`)
  await page.fill('#id_username', email)
  await page.fill('#id_password', password)
  await page.click('button[type=submit]')
  await page.waitForLoadState('networkidle')
  const shot = async (name, clip) => {
    await page.addStyleTag({ content: '*{animation:none!important;transition:none!important}' })
    await page.waitForTimeout(300)
    await page.screenshot({ path: `${OUT}/${name}.png`, ...(clip ? { clip } : {}) })
  }
  const box = async (locator) => pad(await (typeof locator === 'string' ? page.locator(locator).first() : locator).boundingBox())
  const go = async (url) => { await page.goto(B + url); await page.waitForLoadState('networkidle') }
  return { page, shot, box, go }
}

async function pageId(page, title) {
  return page.evaluate(async (t) => {
    const r = await fetch('/admin/api/main/pages/?search=' + encodeURIComponent(t))
    return (await r.json()).items.find((p) => p.title === t)?.id
  }, title)
}

// --- Installation guide (superuser) ------------------------------------------------
{
  const { page, shot, box, go } = await session(process.env.DEMO_ADMIN_EMAIL, process.env.DEMO_ADMIN_PASSWORD)
  await go('/admin/supertext/')
  await page.getByRole('button', { name: 'Test connection' }).click()
  await page.waitForLoadState('networkidle')
  // The docs run against a local stand-in API; show the endpoint users will see.
  await page.evaluate((live) => document.querySelectorAll('code').forEach((c) => { if (c.textContent.includes('127.0.0.1')) c.textContent = live }), LIVE_API)
  await shot('settings-supertext', { x: 0, y: 0, width: 1280, height: 640 })

  await go('/admin/locales/')
  await shot('locales', { x: 0, y: 0, width: 1280, height: 420 })
}

// --- User guide (editor) ---------------------------------------------------------------
{
  const { page, shot, box, go } = await session(process.env.DEMO_EDITOR_EMAIL, process.env.DEMO_EDITOR_PASSWORD)
  await go('/admin/')
  const id = await pageId(page, 'Swiss chocolate, shipped worldwide')

  await go(`/admin/pages/${id}/edit/`)
  await page.locator('header [data-controller~="w-dropdown"] button').first().click()
  await page.getByRole('link', { name: 'Translate this page' }).waitFor()
  await shot('translate-menu', { x: 200, y: 0, width: 640, height: 420 })

  await page.getByRole('link', { name: 'Translate this page' }).click()
  await page.waitForLoadState('networkidle')
  await page.getByLabel('Select all').check()
  await shot('translate-locales', { x: 200, y: 0, width: 1000, height: 440 })
  await page.getByRole('button', { name: 'Submit' }).click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)
  await shot('submitted', { x: 200, y: 0, width: 1080, height: 300 })

  // Open the German translation: the translation editor
  const germanId = await page.evaluate(async () => {
    const r = await fetch('/admin/api/main/pages/?type=home.ArticlePage&locale=de-ch')
    return (await r.json()).items[0]?.id
  })
  await go(`/admin/pages/${germanId}/edit/`)
  await page.waitForTimeout(1500)
  await shot('translation-editor', { x: 200, y: 0, width: 1080, height: 860 })

  await page.getByRole('button', { name: 'Translate with Supertext' }).click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1500)
  await shot('translated-strings', { x: 200, y: 0, width: 1080, height: 860 })
  await page.mouse.wheel(0, 700)
  await page.waitForTimeout(800)
  await shot('translated-body', { x: 200, y: 0, width: 1080, height: 860 })

  // Publish and show the German page on the site
  await page.getByRole('button', { name: /^Publish in / }).click()
  await page.waitForLoadState('networkidle')
  const german = await page.evaluate(async () => {
    const r = await fetch('/admin/api/main/pages/?search=Schweizer')
    return (await r.json()).items[0]?.meta?.html_url
  })
  await page.goto(B + new URL(german).pathname)
  await page.waitForLoadState('networkidle')
  await shot('translated-page', { x: 0, y: 0, width: 1280, height: 640 })
}

await browser.close()
console.log(`Screenshots written to ${OUT}`)
