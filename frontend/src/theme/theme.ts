// MintHRM shared design system — ported from the Payroll Process module so the
// Report Builder matches the rest of the platform (teal #007499, Inter, pill
// inputs, soft cards). Keep this in sync with the platform theme.
import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    primary: { main: "#007499", light: "#3390AD", dark: "#005F7A" },
    secondary: { main: "#6B7280", light: "#9CA3AF", dark: "#4B5563" },
    success: { main: "#007499", light: "#EDF7F0" },
    warning: { main: "#E07912", light: "#FFF8F0" },
    error: { main: "#C13515", light: "#FFF0ED" },
    background: { default: "#F9FAFB", paper: "#FFFFFF" },
    text: { primary: "#1A1A1A", secondary: "#6B7280" },
    divider: "#E5E7EB",
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: 13,
    h4: { fontWeight: 600, fontSize: "1.5rem", color: "#1A1A1A", letterSpacing: "-0.02em" },
    h6: { fontWeight: 600, fontSize: "1.05rem", color: "#1A1A1A" },
    body1: { fontSize: "0.9rem", color: "#1A1A1A" },
    body2: { fontSize: "0.8rem", color: "#6B7280" },
    caption: { fontSize: "0.7rem", color: "#6B7280" },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCssBaseline: { styleOverrides: { body: { backgroundColor: "#F9FAFB" } } },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12, border: "1px solid #E5E7EB", boxShadow: "none",
          transition: "box-shadow 0.2s ease",
          "&:hover": { boxShadow: "0 4px 12px rgba(0,0,0,0.06)" },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8, textTransform: "none", fontWeight: 600, fontSize: "0.82rem",
          boxShadow: "none", "&:hover": { boxShadow: "none" },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500, fontSize: "0.72rem", borderRadius: 50, height: 32,
          backgroundColor: "#F0F0F0", color: "#374151", border: "none",
          "&:hover": { backgroundColor: "#E5E5E5" },
        },
        sizeSmall: { height: 26, fontSize: "0.65rem" },
        colorPrimary: { backgroundColor: "#007499", color: "#fff", "&:hover": { backgroundColor: "#005F7A" } },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { fontSize: "0.8rem", borderColor: "#E5E7EB", padding: "10px 14px" },
        head: {
          fontWeight: 600, color: "#374151", backgroundColor: "#F9FAFB",
          fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.3px",
        },
      },
    },
    MuiTableRow: { styleOverrides: { root: { "&:hover": { backgroundColor: "#F9FAFB !important" } } } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          fontSize: "0.8rem", borderRadius: 50, backgroundColor: "#F9FAFB", paddingLeft: 8,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: "#E5E7EB", borderWidth: 1 },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "#D1D5DB" },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: "#007499", borderWidth: 1.5 },
        },
      },
    },
    MuiSelect: { styleOverrides: { root: { borderRadius: 50 } } },
    MuiInputLabel: {
      styleOverrides: { root: { fontSize: "0.8rem", fontWeight: 500, color: "#6B7280", left: 8 } },
    },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 12 } } },
  },
});

export default theme;
