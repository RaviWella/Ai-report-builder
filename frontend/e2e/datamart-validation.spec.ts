import { test, expect } from '@playwright/test'

const baseURL = process.env.DATAMART_E2E_URL ?? 'http://localhost:5174'
const orgQuery = 'organization_id=alpha&environment=development'

/**
 * UI test for validation badge — mocks chat API so no LLM/warehouse required.
 * Run with frontend dev server: DATAMART_E2E_URL=http://localhost:5174 npx playwright test e2e/datamart-validation.spec.ts
 */
test.describe('Datamart validation UI', () => {
  test.setTimeout(60_000)

  test('shows trust badge when chat response includes validation', async ({ page }) => {
    await page.route('**/api/v1/datamart/chat', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          question: 'Show employees',
          narrative: 'Here are employees.',
          sql: 'SELECT employee_id FROM dim_employee LIMIT 10',
          columns: ['employee_id'],
          rows: [[1], [2]],
          row_count: 2,
          session_id: 'e2e-validation-session',
          message_id: 'e2e-validation-msg',
          turn_index: 0,
          validation: {
            retrieval: {
              status: 'sufficient',
              tables_selected: ['dim_employee'],
              warnings: [],
            },
            generation: {
              binding: 'passed',
              warnings: [],
              truncated: false,
              grounding_expanded: false,
            },
            overall: 'plausible',
          },
        }),
      })
    })

    await page.route('**/api/v1/datamart/sessions**', async (route) => {
      if (route.request().method() === 'GET' && route.request().url().includes('/messages')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ messages: [], has_more: false, page: 1, page_size: 5 }),
        })
        return
      }
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ sessions: [] }),
        })
        return
      }
      await route.continue()
    })

    await page.route('**/api/v1/datamart/suggestions**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ questions: [] }),
      })
    })

    await page.route('**/api/v1/datamart/bootstrap**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          profile: 'tenant_etl',
          tenant_id: 'demo_tenant',
          ready: true,
          table_count: 10,
        }),
      })
    })

    await page.goto(`${baseURL}/datamart/chat?${orgQuery}`, {
      waitUntil: 'domcontentloaded',
    })

    const composer = page.getByTestId('datamart-composer-input')
    await expect(composer).toBeVisible({ timeout: 30_000 })
    await composer.fill('Show employees')
    await page.getByTestId('datamart-composer-send').click()

    const badge = page.getByTestId('datamart-validation-badge').last()
    await expect(badge).toBeVisible({ timeout: 15_000 })
    await expect(badge).toHaveAttribute('data-trust', 'plausible')

    const panel = page.getByTestId('datamart-validation-panel').last()
    await expect(panel).toBeVisible()
    await panel.locator('button').first().click()
    await expect(panel.getByText(/dim_employee/i)).toBeVisible({ timeout: 10_000 })
  })
})
