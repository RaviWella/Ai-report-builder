/** Parse template id from /datamart/templates/:id (pathname is authoritative when params lag). */
export function templateIdFromPathname(pathname: string): string | null {
  const match = pathname.match(/\/datamart\/templates\/([^/?#]+)/)
  return match?.[1] ?? null
}
