import { test, expect } from '@playwright/test'

const baseURL = process.env.DATAMART_E2E_URL ?? 'http://localhost:5174'
const apiKey = process.env.DATAMART_E2E_API_KEY ?? 'hrm-dev-api-key'
const orgQuery = 'organization_id=alpha&environment=development'

test.describe('Datamart session navigation', () => {
  test.setTimeout(90_000)

  test('sidebar switches chat workspace when clicking another session', async ({
    page,
    request,
  }) => {
    const listRes = await request.get(`${baseURL.replace(/\/$/, '')}/api/v1/datamart/sessions`, {
      headers: { 'X-API-Key': apiKey },
    })
    test.skip(!listRes.ok(), `Sessions API unavailable (${listRes.status()})`)

    const body = (await listRes.json()) as { sessions: Array<{ id: string }> }
    test.skip(body.sessions.length < 2, 'Need at least 2 chat sessions')

    const [first, second] = body.sessions

    await page.goto(`${baseURL}/datamart/chat?session=${first.id}&${orgQuery}`)

    const root = page.getByTestId('datamart-chat-root')
    await expect(root).toHaveAttribute('data-session-id', first.id, { timeout: 30_000 })

    await page
      .getByTestId(`datamart-session-row-${second.id}`)
      .locator('a')
      .click()

    await expect(page).toHaveURL(new RegExp(`session=${second.id}`), { timeout: 15_000 })
    await expect(root).toHaveAttribute('data-session-id', second.id, { timeout: 30_000 })

    await page
      .getByTestId(`datamart-session-row-${first.id}`)
      .locator('a')
      .click()
    await expect(page).toHaveURL(new RegExp(`session=${first.id}`), { timeout: 15_000 })
    await expect(root).toHaveAttribute('data-session-id', first.id, { timeout: 30_000 })
  })
})
