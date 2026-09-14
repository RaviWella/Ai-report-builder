import { test, expect } from '@playwright/test'

/**
 * Live E2E for datamart report flow. Skipped unless DATAMART_E2E_URL is set and
 * the stack is running with a seeded tenant + auth cookies (or storage state).
 */
const e2eEnabled = !!process.env.DATAMART_E2E_URL

test.describe('Datamart report flow', () => {
  test.skip(!e2eEnabled, 'Set DATAMART_E2E_URL to run live datamart E2E')

  test('new session → ask → run → remove column → run again', async ({ page }) => {
    await page.goto('/datamart/chat')

    const composer = page.getByTestId('datamart-composer-input')
    await composer.fill('Show employee names and leave days for this month')
    await page.getByTestId('datamart-composer-send').click()

    const reportCard = page.getByTestId('datamart-report-card').last()
    await expect(reportCard).toBeVisible({ timeout: 120_000 })

    await page.getByTestId('datamart-run-query').last().click()
    await expect(reportCard.getByRole('table')).toBeVisible({ timeout: 60_000 })

    await page.getByTestId('datamart-quick-remove-column').click()
    const firstColumnChip = page
      .getByTestId('datamart-quick-actions')
      .locator('button')
      .filter({ hasText: /^[a-z_]+$/i })
      .first()
    await firstColumnChip.click()

    await expect(composer).not.toHaveValue('')
    await page.getByTestId('datamart-composer-send').click()

    await expect(page.getByTestId('datamart-report-card').last()).toBeVisible({
      timeout: 120_000,
    })
    await page.getByTestId('datamart-run-query').last().click()
    await expect(page.getByTestId('datamart-report-card').last().getByRole('table')).toBeVisible({
      timeout: 60_000,
    })
  })
})
