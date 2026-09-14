import { test, expect } from '@playwright/test'

/**
 * Template sidebar navigation — requires dev stack at DATAMART_E2E_URL (default :5174).
 * Uses API key auth via env; no login flow.
 */
const baseURL = process.env.DATAMART_E2E_URL ?? 'http://localhost:5174'
const apiKey = process.env.DATAMART_E2E_API_KEY ?? 'hrm-dev-api-key'

test.describe('Datamart template navigation', () => {
  test.setTimeout(90_000)

  test('sidebar switches template workspace when clicking another template', async ({
    page,
    request,
  }) => {
    const listRes = await request.get(`${baseURL.replace(/\/$/, '')}/api/v1/datamart/templates`, {
      headers: { 'X-API-Key': apiKey },
    })
    test.skip(!listRes.ok(), `Templates API unavailable (${listRes.status()})`)

    const body = (await listRes.json()) as { templates: Array<{ id: string; name: string }> }
    test.skip(body.templates.length < 2, 'Need at least 2 templates in the tenant')

    const [first, second] = body.templates

    const orgQuery = 'organization_id=alpha&environment=development'
    await page.goto(`${baseURL}/datamart/templates/${first.id}?${orgQuery}`)

    const header = page.getByTestId('datamart-template-title')
    await expect(header).toHaveText(first.name, { timeout: 30_000 })

    await page
      .getByTestId(`datamart-template-row-${second.id}`)
      .locator('a')
      .click()

    await expect(page).toHaveURL(new RegExp(`/datamart/templates/${second.id}(\\?|$)`), {
      timeout: 15_000,
    })
    await expect(header).toHaveAttribute('data-template-id', second.id, { timeout: 15_000 })
    await expect(header).toHaveText(second.name, { timeout: 30_000 })

    await page
      .getByTestId(`datamart-template-row-${first.id}`)
      .locator('a')
      .click()
    await expect(page).toHaveURL(new RegExp(`/datamart/templates/${first.id}(\\?|$)`), {
      timeout: 15_000,
    })
    await expect(header).toHaveText(first.name, { timeout: 30_000 })
  })
})
