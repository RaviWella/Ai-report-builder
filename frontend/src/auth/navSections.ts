/** Report Builder sidebar section flags (must match backend NAV_SECTION_KEYS). */

export type NavSectionFlags = Record<string, boolean>;

/** Tenant-grantable sections only — Config / AI Settings live under Observations. */
export const DEFAULT_NAV_SECTION_FLAGS: NavSectionFlags = {
  Chat: false,
  Builder: false,
  Documents: true,
  Viewer: true,
  "How it works": false,
};

/** Sidebar label for a builder path. Used only for tests / mapping — flags never block routes. */
export function sectionForPath(pathname: string): string | null {
  if (pathname === "/" || pathname === "") return "Templates";
  if (pathname === "/chat" || pathname.startsWith("/chat/")) return "Chat";
  if (pathname.startsWith("/builder") || pathname.startsWith("/rule-reports")) return "Builder";
  if (pathname === "/documents" || pathname.startsWith("/documents/")) return "Documents";
  if (pathname === "/viewer" || pathname.startsWith("/viewer/")) return "Viewer";
  if (pathname === "/how-it-works" || pathname.startsWith("/how-it-works/")) return "How it works";
  return null;
}

export function resolveNavFlags(navSections: NavSectionFlags | undefined | null): NavSectionFlags {
  if (!navSections || typeof navSections !== "object" || Array.isArray(navSections)) {
    return { ...DEFAULT_NAV_SECTION_FLAGS };
  }
  const merged = { ...DEFAULT_NAV_SECTION_FLAGS };
  for (const key of Object.keys(DEFAULT_NAV_SECTION_FLAGS)) {
    if (key in navSections) merged[key] = Boolean(navSections[key]);
  }
  return merged;
}

/** Templates is always visible; other sections require an explicit true flag. */
export function isSectionAllowed(
  navSections: NavSectionFlags | undefined | null,
  section: string,
): boolean {
  if (section === "Templates") return true;
  // Config / AI Settings are never tenant-grantable (admin Observations only).
  if (section === "Config" || section === "AI Settings") return false;
  const flags = resolveNavFlags(navSections);
  return flags[section] === true;
}
