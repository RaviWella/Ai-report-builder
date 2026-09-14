import { test, expect } from '@playwright/test'

/**
 * End-to-end: alternate between chat sessions and templates without either mode breaking.
 */
const baseURL = process.env.DATAMART_E2E_URL ?? 'http://localhost:5174'
const apiKey = process.env.DATAMART_E2E_API_KEY ?? 'hrm-dev-api-key'
const orgQuery = 'organization_id=alpha&environment=development'

test.describe('Datamart workspace navigation (chat + templates)', () => {
  test.setTimeout(120_000)

  test('alternates session → template → session → template', async ({ page, request }) => {
    const [sessionsRes, templatesRes] = await Promise.all([
      request.get(`${baseURL}/api/v1/datamart/sessions`, {
        headers: { 'X-API-Key': apiKey },
      }),
      request.get(`${baseURL}/api/v1/datamart/templates`, {
        headers: { 'X-API-Key': apiKey },
      }),
    ])
    test.skip(!sessionsRes.ok() || !templatesRes.ok(), 'API unavailable')

    const sessions = ((await sessionsRes.json()) as { sessions: Array<{ id: string }> })
      .sessions
    const templates = ((await templatesRes.json()) as { templates: Array<{ id: string; name: string }> })
      .templates
    test.skip(sessions.length < 2 || templates.length < 2, 'Need 2+ sessions and templates')

    const [sessionA, sessionB] = sessions
    const [templateA, templateB] = templates

    await page.goto(
      `${baseURL}/datamart/chat?session=${sessionA.id}&${orgQuery}`,
    )

    const chatRoot = page.getByTestId('datamart-chat-root')
    const templateTitle = page.getByTestId('datamart-template-title')

    await expect(chatRoot).toHaveAttribute('data-session-id', sessionA.id, {
      timeout: 30_000,
    })

    // Chat → template A
    await page
      .getByTestId(`datamart-template-row-${templateA.id}`)
      .locator('a')
      .click()
    await expect(page).toHaveURL(new RegExp(`/datamart/templates/${templateA.id}`), {
      timeout: 15_000,
    })
    await expect(templateTitle).toHaveAttribute('data-template-id', templateA.id, {
      timeout: 30_000,
    })
    await expect(templateTitle).toHaveText(templateA.name, { timeout: 30_000 })

    // Template → session B
    await page
      .getByTestId(`datamart-session-row-${sessionB.id}`)
      .locator('a')
      .click()
    await expect(page).toHaveURL(new RegExp(`session=${sessionB.id}`), {
      timeout: 15_000,
    })
    await expect(chatRoot).toHaveAttribute('data-session-id', sessionB.id, {
      timeout: 30_000,
    })

    // Chat → template B
    await page
      .getByTestId(`datamart-template-row-${templateB.id}`)
      .locator('a')
      .click()
    await expect(page).toHaveURL(new RegExp(`/datamart/templates/${templateB.id}`), {
      timeout: 15_000,
    })
    await expect(templateTitle).toHaveAttribute('data-template-id', templateB.id, {
      timeout: 30_000,
    })
    await expect(templateTitle).toHaveText(templateB.name, { timeout: 30_000 })

    // Template → session A
    await page
      .getByTestId(`datamart-session-row-${sessionA.id}`)
      .locator('a')
      .click()
    await expect(page).toHaveURL(new RegExp(`session=${sessionA.id}`), {
      timeout: 15_000,
    })
    await expect(chatRoot).toHaveAttribute('data-session-id', sessionA.id, {
      timeout: 30_000,
    })
  })
})
