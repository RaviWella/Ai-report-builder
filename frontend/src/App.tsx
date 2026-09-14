import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { hasFullNavAccess, syncActiveTenantFromAuth } from "./lib/activeTenant";
import RequireAuth from "./components/RequireAuth";
import Layout from "./components/Layout";
import AuthLaunch from "./pages/AuthLaunch";
import HRDashboard from "./pages/hr-reports/HRDashboard";
import EmployeesReport from "./pages/hr-reports/EmployeesReport";
import SalaryBandsReport from "./pages/hr-reports/SalaryBandsReport";
import LifecycleReport from "./pages/hr-reports/LifecycleReport";
import HeadcountReport from "./pages/hr-reports/HeadcountReport";
import TurnoverReport from "./pages/hr-reports/TurnoverReport";
import PayrollReport from "./pages/hr-reports/PayrollReport";
import AttendanceReport from "./pages/hr-reports/AttendanceReport";
import LeaveReport from "./pages/hr-reports/LeaveReport";
import PerformanceReport from "./pages/hr-reports/PerformanceReport";
import CustomizedReports from "./pages/hr-reports/CustomizedReports";
import CustomReportPreviewPage from "./pages/hr-reports/CustomReportPreviewPage";
import CustomReportDefinitions from "./pages/CustomReportDefinitions";
import ETLControl from "./pages/ETLControl";
import EtlSources from "./pages/EtlSources";
import DatamartWorkspace from "./pages/datamart/DatamartWorkspace";

function HomeRedirect() {
  return (
    <Navigate to={hasFullNavAccess() ? "/hr/dashboard" : "/hr/custom-reports"} replace />
  );
}

function App() {
  useEffect(() => {
    syncActiveTenantFromAuth();
  }, []);

  return (
    <Routes>
      <Route path="/auth" element={<AuthLaunch />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<HomeRedirect />} />

        <Route path="hr/dashboard" element={<HRDashboard />} />
        <Route path="hr/workforce" element={<Navigate to="/hr/headcount" replace />} />
        <Route path="hr/employees" element={<EmployeesReport />} />
        <Route path="hr/salary-bands" element={<SalaryBandsReport />} />
        <Route path="hr/lifecycle" element={<LifecycleReport />} />
        <Route path="hr/headcount" element={<HeadcountReport />} />
        <Route path="hr/turnover" element={<TurnoverReport />} />
        <Route path="hr/payroll" element={<PayrollReport />} />
        <Route path="hr/attendance" element={<AttendanceReport />} />
        <Route path="hr/leave" element={<LeaveReport />} />
        <Route path="hr/performance" element={<PerformanceReport />} />
        <Route path="hr/custom-reports" element={<CustomizedReports />} />
        <Route
          path="hr/payroll/custom-reports"
          element={<Navigate to="/hr/custom-reports" replace />}
        />
        <Route path="hr/custom-reports/:viewName" element={<CustomReportPreviewPage />} />
        <Route path="hr/experience" element={<Navigate to="/hr/dashboard" replace />} />
        <Route path="datamart/chat" element={<DatamartWorkspace />} />
        <Route
          path="datamart/templates/:templateId"
          element={<DatamartWorkspace />}
        />
        <Route path="etl/control" element={<ETLControl />} />
        <Route path="settings/etl-sources" element={<EtlSources />} />
        <Route path="settings/custom-reports" element={<CustomReportDefinitions />} />
        <Route path="settings/connections" element={<Navigate to="/settings/etl-sources" replace />} />
        <Route path="settings/source" element={<Navigate to="/settings/etl-sources" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
