/**
 * Normalizes API / network errors for user-visible messages (datamart).
 */
import { getErrorMessage } from '../../../services/api'

export function formatApiError(error: unknown, fallback = 'Something went wrong.'): string {
  const msg = getErrorMessage(error)
  if (!msg || msg === 'An unknown error occurred') return fallback
  return msg
}
