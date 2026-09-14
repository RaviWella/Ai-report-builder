import type { Me } from "../api/client";

export function isSupportAdmin(me: Me | null | undefined): boolean {
  return me?.role === "support_admin";
}
