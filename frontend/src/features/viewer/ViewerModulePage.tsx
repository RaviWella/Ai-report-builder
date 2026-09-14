// Report names for the selected module (top-link). Click a name -> view it.
import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Card, CardActionArea, CardContent, Stack, Typography } from "@mui/material";
import { DescriptionOutlined, ChevronRight } from "@mui/icons-material";
import { templateApi } from "../../api/client";

interface Tpl { id: string; name: string; description?: string; module?: string; current_published_version_id: string | null; }

export function ViewerModulePage() {
  const { module = "" } = useParams();
  const navigate = useNavigate();
  const { data: templates = [] } = useQuery({ queryKey: ["templates"], queryFn: templateApi.list });

  const reports = (templates as Tpl[]).filter(
    (t) => (t.module || "General") === module && t.current_published_version_id,
  );

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 0.5 }}>{module} Reports</Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>Select a report to view and download.</Typography>

      <Stack spacing={1.25}>
        {reports.map((t) => (
          <Card key={t.id}>
            <CardActionArea onClick={() => navigate(`/viewer/r/${t.id}`)}>
              <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 }, display: "flex", alignItems: "center", gap: 1.5 }}>
                <DescriptionOutlined sx={{ color: "#007499" }} />
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ fontWeight: 600, fontSize: "0.92rem" }}>{t.name}</Typography>
                  <Typography variant="body2">{t.description || "—"}</Typography>
                </Box>
                <ChevronRight sx={{ color: "#9CA3AF" }} />
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
        {reports.length === 0 && <Typography variant="body2">No published reports in {module}.</Typography>}
      </Stack>
    </Box>
  );
}
