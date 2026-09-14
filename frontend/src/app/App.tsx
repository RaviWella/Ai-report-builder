// Shells:
//  - /viewer/*              -> end-user Report Viewer
//  - /settings/*            -> Admin tools (Permission handler + Observations)
//  - /*                     -> Report Builder (tenant sidebar)
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { Box, CircularProgress, Typography } from "@mui/material";
import { TouchAppOutlined } from "@mui/icons-material";
import { MainLayout } from "../layouts/MainLayout";
import { AdminToolsLayout } from "../layouts/AdminToolsLayout";
import { BuilderPage } from "../features/builder/BuilderPage";
import { ConversationalBuilder } from "../features/builder/ConversationalBuilder";
import { RuleReportBuilder } from "../features/builder/RuleReportBuilder";
import { LegacySqlConverterPage } from "../features/builder/LegacySqlConverterPage";
import { TemplatesPage } from "../features/templates/TemplatesPage";
import { DocumentsPage } from "../features/documents/DocumentsPage";
import { DocumentBuilder } from "../features/documents/DocumentBuilder";
const CanvasDesigner = lazy(() =>
  import("../features/documents/CanvasDesigner").then((m) => ({ default: m.CanvasDesigner })),
);
import { MetricsPage } from "../features/metrics/MetricsPage";
import { GlossaryPage } from "../features/glossary/GlossaryPage";
import { DataHealthPage } from "../features/health/DataHealthPage";
import { AISettings } from "../features/settings/AISettings";
import { PermissionsSettings } from "../features/settings/PermissionsSettings";
import { ObservationsHome, ObservationsShell } from "../features/settings/ObservationsShell";
import { HowItWorks } from "../features/docs/HowItWorks";
import { ViewerLayout } from "../features/viewer/ViewerLayout";
import { ViewerModulePage } from "../features/viewer/ViewerModulePage";
import { ViewerReportPage } from "../features/viewer/ViewerReportPage";
import { ViewerPage } from "../features/viewer/ViewerPage";

function ViewerLegacyRedirect() {
  const { templateId = "" } = useParams();
  return <Navigate to={`/viewer/r/${templateId}`} replace />;
}

/** Remount the editor on each navigation (incl. browser Back) so saved state
 *  never survives a route change and the report is always re-fetched fresh. */
function RuleReportEditorRoute() {
  const { templateId } = useParams();
  const location = useLocation();
  return <RuleReportBuilder key={`${templateId ?? "new"}:${location.key}`} />;
}

function ViewerHome() {
  return (
    <Box sx={{ textAlign: "center", py: 8, color: "text.secondary" }}>
      <TouchAppOutlined sx={{ fontSize: 40, color: "#007499" }} />
      <Typography sx={{ mt: 1, fontWeight: 600 }}>Pick a module above</Typography>
      <Typography variant="body2">Open a module to see its reports, then choose one to view.</Typography>
    </Box>
  );
}

function BuilderShell() {
  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<TemplatesPage />} />
        <Route path="/chat" element={<ConversationalBuilder />} />
        <Route path="/builder" element={<BuilderPage />} />
        <Route path="/builder/:templateId" element={<BuilderPage />} />
        <Route path="/rule-reports/new" element={<RuleReportEditorRoute />} />
        <Route path="/rule-reports/:templateId" element={<RuleReportEditorRoute />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/report/new" element={<DocumentBuilder />} />
        <Route path="/documents/report/:id/edit" element={<DocumentBuilder />} />
        <Route path="/documents/design/new" element={
          <Suspense fallback={<Box sx={{ textAlign: "center", py: 8 }}><CircularProgress /></Box>}><CanvasDesigner /></Suspense>
        } />
        <Route path="/documents/design/:id/edit" element={
          <Suspense fallback={<Box sx={{ textAlign: "center", py: 8 }}><CircularProgress /></Box>}><CanvasDesigner /></Suspense>
        } />
        <Route path="/documents/new" element={<DocumentBuilder />} />
        <Route path="/documents/:id/edit" element={<DocumentBuilder />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        {/* Legacy Config / AI paths → Observations (admin tools) */}
        <Route path="/settings/ai" element={<Navigate to="/settings/observations/ai" replace />} />
        <Route path="/metrics" element={<Navigate to="/settings/observations/metrics" replace />} />
        <Route path="/glossary" element={<Navigate to="/settings/observations/glossary" replace />} />
        <Route path="/data-health" element={<Navigate to="/settings/observations/data-health" replace />} />
        <Route path="/legacy-sql" element={<Navigate to="/settings/observations/legacy-sql" replace />} />
        <Route path="/viewer/r/:templateId" element={<ViewerReportPage />} />
        <Route path="/viewer/m/:module" element={<ViewerModulePage />} />
        <Route path="/viewer/:templateId" element={<ViewerLegacyRedirect />} />
        <Route path="/viewer" element={<ViewerPage />} />
      </Routes>
    </MainLayout>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/viewer" element={<ViewerLayout />}>
        <Route index element={<ViewerHome />} />
        <Route path="m/:module" element={<ViewerModulePage />} />
        <Route path="r/:templateId" element={<ViewerReportPage />} />
        <Route path=":templateId" element={<ViewerLegacyRedirect />} />
      </Route>

      {/* Admin tools console — own sidebar (Permission handler + Observations) */}
      <Route path="/settings" element={<AdminToolsLayout />}>
        <Route index element={<Navigate to="permissions" replace />} />
        <Route path="permissions" element={<PermissionsSettings />} />
        <Route path="observations" element={<ObservationsShell />}>
          <Route index element={<ObservationsHome />} />
          <Route path="ai" element={<AISettings />} />
          <Route path="metrics" element={<MetricsPage />} />
          <Route path="glossary" element={<GlossaryPage />} />
          <Route path="data-health" element={<DataHealthPage />} />
          <Route path="legacy-sql" element={<LegacySqlConverterPage />} />
        </Route>
        <Route path="*" element={<Navigate to="permissions" replace />} />
      </Route>

      <Route path="/*" element={<BuilderShell />} />
    </Routes>
  );
}
