import { Navigate, useLocation } from "react-router-dom";
import { getStoredAuthToken } from "../lib/activeTenant";
import { SKIP_AUTH } from "../env";

interface RequireAuthProps {
  children: React.ReactNode;
}

/**
 * In production, users must arrive via /auth?payload= from MinHRM HRIS.
 * Dev: REACT_APP_SKIP_AUTH=true + MOCK_AUTH_ENABLED on API.
 */

export default function RequireAuth({ children }: RequireAuthProps) {
  const location = useLocation();
  const token = getStoredAuthToken();

  if (!SKIP_AUTH && !token) {
    return <Navigate to="/auth" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}
