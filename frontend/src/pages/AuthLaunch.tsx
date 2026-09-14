import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { applyUserAuth, hasFullNavAccess } from "../lib/activeTenant";
import { setTenantBranding } from "../lib/tenantBranding";
import { getErrorMessage, hrApi } from "../services/api";
import { SKIP_AUTH, TENANT_ID } from "../env";

export default function AuthLaunch() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (SKIP_AUTH) {
      applyUserAuth(TENANT_ID);
      const target = hasFullNavAccess() ? "/hr/dashboard" : "/hr/custom-reports";
      navigate(target, { replace: true });
      window.history.replaceState({}, "", target);
      return () => {
        cancelled = true;
      };
    }

    let payload = searchParams.get("payload");
    if (!payload) {
      setError("Missing launch payload. Open analytics from the MinHRM warehouse widget.");
      return;
    }
    // Query parsers can turn base64 '+' into spaces.
    if (payload.includes(" ") && !payload.includes("+")) {
      payload = payload.replace(/ /g, "+");
    }

    const subdomain = searchParams.get("subdomain") ?? undefined;
    const employeeId = searchParams.get("employee_id") ?? undefined;

    (async () => {
      try {
        const res = await hrApi.verifyLaunchPayload({
          payload,
          subdomain,
          employee_id: employeeId,
        });
        if (cancelled) return;

        applyUserAuth(res.tenant_id, res.access_token);
        setTenantBranding(res.branding);

        const target = hasFullNavAccess() ? "/hr/dashboard" : "/hr/custom-reports";

        navigate(target, { replace: true });
        window.history.replaceState({}, "", target);
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm text-center">
        {error ? (
          <>
            <h1 className="text-lg font-semibold text-slate-900">Sign-in failed</h1>
            <p className="mt-3 text-sm text-red-700">{error}</p>
            <p className="mt-4 text-xs text-slate-500">
              Return to MinHRM and open the warehouse analytics widget again.
            </p>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto animate-spin text-teal-600" size={32} />
            <p className="mt-4 text-sm text-slate-600">Signing you in…</p>
          </>
        )}
      </div>
    </div>
  );
}
