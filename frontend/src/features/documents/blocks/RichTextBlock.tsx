// A rich-text canvas block (TipTap) with a Word-like toolbar: bold/italic/underline/
// strikethrough, headings, lists, alignment and text colour — plus data binding:
//   • "{}"  — insert a {{field}} token at the cursor
//   • select text -> "Make dynamic" bubble binds the selection to a field
// Content is HTML on the block; tokens are substituted per record at render time.
import { useState } from "react";
import { useEditor, EditorContent, BubbleMenu, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import TextStyle from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import Image from "@tiptap/extension-image";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableHeader from "@tiptap/extension-table-header";
import TableCell from "@tiptap/extension-table-cell";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Box, IconButton, Divider, Popover, Paper, Button, Autocomplete, TextField, Stack, Tooltip,
} from "@mui/material";
import {
  FormatBold, FormatItalic, FormatUnderlined, StrikethroughS, FormatListBulleted,
  FormatListNumbered, Title, DataObjectOutlined, AutoFixHigh, FormatColorText,
  FormatAlignLeft, FormatAlignCenter, FormatAlignRight, ImageOutlined, TableChartOutlined,
  Remove, SpaceBar,
} from "@mui/icons-material";
import type { SemanticFieldMeta } from "../../../types/spec";
import { preparePastedLetterHtml, sanitizeLetterHtml } from "../letterHtml";
import { MergeTokenHighlight } from "./MergeTokenHighlight";
import { ValueMapPopover } from "../ValueMapPopover";

export function RichTextBlock({
  html, onChange, fields, autoFocus, registerEditor, onFocusBlock,
}: {
  html: string;
  onChange: (html: string) => void;
  fields: SemanticFieldMeta[];
  autoFocus?: boolean;
  registerEditor?: (editor: Editor | null) => void;
  onFocusBlock?: () => void;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextStyle,
      Color,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Image,
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({
        placeholder: "Type your letter here, or paste content from Word / a PDF (English, Tamil or Sinhala)…",
      }),
      MergeTokenHighlight,
    ],
    content: sanitizeLetterHtml(html || "<p></p>"),
    autofocus: autoFocus ? "end" : false,
    editorProps: {
      transformPastedHTML: (pasted) => preparePastedLetterHtml(pasted),
    },
    onUpdate: ({ editor }) => onChange(sanitizeLetterHtml(editor.getHTML())),
    onCreate: ({ editor }) => registerEditor?.(editor),
    onFocus: () => onFocusBlock?.(),
    onDestroy: () => registerEditor?.(null),
  });
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [replacing, setReplacing] = useState(false);
  const [mapField, setMapField] = useState<SemanticFieldMeta | null>(null);

  if (!editor) return null;
  const insertToken = (tokenInner: string) => {
    editor.chain().focus().unsetColor().insertContent(`{{${tokenInner}}}`).run();
    setAnchor(null);
  };
  const insertField = (ref: string) => insertToken(ref);
  const onFieldPicked = (f: SemanticFieldMeta) => {
    if (f.sample_values?.length) {
      setMapField(f);  // hold the field picker open behind the mapping popover
    } else {
      insertField(f.ref);
    }
  };
  const openPicker = (el: HTMLElement) => {
    setReplacing(!editor.state.selection.empty);
    setAnchor(el);
  };
  const onImage = (file: File) => {
    const r = new FileReader();
    r.onload = () => editor.chain().focus().setImage({ src: String(r.result) }).run();
    r.readAsDataURL(file);
  };

  const c = (active: boolean) => ({ color: active ? "#007499" : "#6B7280", p: 0.5 });
  const isAlign = (a: string) => editor.isActive({ textAlign: a });
  const curColor = editor.getAttributes("textStyle").color || "#1F2937";
  return (
    <Box>
      {/* Selection bubble — turn highlighted fixed text into a data field */}
      <BubbleMenu editor={editor} shouldShow={({ state }) => !state.selection.empty}>
        <Paper elevation={4} sx={{ p: 0.25, borderRadius: 1.5 }}>
          <Button size="small" startIcon={<AutoFixHigh fontSize="small" />}
            onMouseDown={(e) => e.preventDefault()} onClick={(e) => openPicker(e.currentTarget)}
            sx={{ textTransform: "none", px: 1, color: "#7C3AED" }}>
            Make dynamic
          </Button>
        </Paper>
      </BubbleMenu>

      <Stack direction="row" spacing={0} alignItems="center" sx={{ mb: 0.5, flexWrap: "wrap" }}>
        <IconButton size="small" sx={c(editor.isActive("bold"))} onClick={() => editor.chain().focus().toggleBold().run()}><FormatBold fontSize="small" /></IconButton>
        <IconButton size="small" sx={c(editor.isActive("italic"))} onClick={() => editor.chain().focus().toggleItalic().run()}><FormatItalic fontSize="small" /></IconButton>
        <IconButton size="small" sx={c(editor.isActive("underline"))} onClick={() => editor.chain().focus().toggleUnderline().run()}><FormatUnderlined fontSize="small" /></IconButton>
        <IconButton size="small" sx={c(editor.isActive("strike"))} onClick={() => editor.chain().focus().toggleStrike().run()}><StrikethroughS fontSize="small" /></IconButton>
        <Divider orientation="vertical" flexItem sx={{ mx: 0.4 }} />
        <Tooltip title="Heading"><IconButton size="small" sx={c(editor.isActive("heading", { level: 2 }))} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}><Title fontSize="small" /></IconButton></Tooltip>
        <IconButton size="small" sx={c(editor.isActive("bulletList"))} onClick={() => editor.chain().focus().toggleBulletList().run()}><FormatListBulleted fontSize="small" /></IconButton>
        <IconButton size="small" sx={c(editor.isActive("orderedList"))} onClick={() => editor.chain().focus().toggleOrderedList().run()}><FormatListNumbered fontSize="small" /></IconButton>
        <Divider orientation="vertical" flexItem sx={{ mx: 0.4 }} />
        <IconButton size="small" sx={c(isAlign("left"))} onClick={() => editor.chain().focus().setTextAlign("left").run()}><FormatAlignLeft fontSize="small" /></IconButton>
        <IconButton size="small" sx={c(isAlign("center"))} onClick={() => editor.chain().focus().setTextAlign("center").run()}><FormatAlignCenter fontSize="small" /></IconButton>
        <IconButton size="small" sx={c(isAlign("right"))} onClick={() => editor.chain().focus().setTextAlign("right").run()}><FormatAlignRight fontSize="small" /></IconButton>
        <Tooltip title="Text colour">
          <IconButton size="small" component="label" sx={{ p: 0.5, color: curColor }}>
            <FormatColorText fontSize="small" />
            <input type="color" value={curColor} onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
              style={{ position: "absolute", width: 1, height: 1, opacity: 0 }} />
          </IconButton>
        </Tooltip>
        <Divider orientation="vertical" flexItem sx={{ mx: 0.4 }} />
        <Tooltip title="Insert image">
          <IconButton size="small" component="label" sx={{ p: 0.5, color: "#6B7280" }}>
            <ImageOutlined fontSize="small" />
            <input hidden type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && onImage(e.target.files[0])} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Insert table"><IconButton size="small" sx={{ p: 0.5, color: "#6B7280" }} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}><TableChartOutlined fontSize="small" /></IconButton></Tooltip>
        <Tooltip title="Divider line"><IconButton size="small" sx={{ p: 0.5, color: "#6B7280" }} onClick={() => editor.chain().focus().setHorizontalRule().run()}><Remove fontSize="small" /></IconButton></Tooltip>
        <Tooltip title="Blank line (spacer)"><IconButton size="small" sx={{ p: 0.5, color: "#6B7280" }} onClick={() => editor.chain().focus().insertContent("<p></p>").run()}><SpaceBar fontSize="small" /></IconButton></Tooltip>
        <Divider orientation="vertical" flexItem sx={{ mx: 0.4 }} />
        <Tooltip title="Insert a data field — or select text first to turn it into a field">
          <IconButton size="small" sx={{ color: "#007499", p: 0.5 }} onMouseDown={(e) => e.preventDefault()} onClick={(e) => openPicker(e.currentTarget)}><DataObjectOutlined fontSize="small" /></IconButton>
        </Tooltip>
      </Stack>
      <Box sx={{
        "& .ProseMirror": {
          outline: "none", minHeight: 24, fontSize: "0.9rem", lineHeight: 1.5,
          fontFamily: "'Helvetica Neue', Arial, 'Noto Sans Tamil', 'Noto Sans Sinhala', sans-serif",
        },
        // Greyed hint shown only while the editor is empty (first paragraph).
        "& .ProseMirror p.is-editor-empty:first-of-type::before": {
          content: "attr(data-placeholder)", float: "left", color: "#9CA3AF",
          pointerEvents: "none", height: 0,
        },
        "& .ProseMirror p": { m: "0 0 4px" },
        "& .ProseMirror .merge-token": {
          background: "#E6F3F7", color: "#036 !important", borderRadius: "4px",
          padding: "0 4px", fontFamily: "ui-monospace, monospace", fontSize: "0.92em",
        },
        "& .ProseMirror .merge-token--word": {
          background: "#FEF3C7", color: "#92400E !important",
        },
        "& .ProseMirror:focus": { outline: "none" },
        "& .ProseMirror img": { maxWidth: "100%", height: "auto" },
        "& .ProseMirror table": { borderCollapse: "collapse", width: "100%", margin: "8px 0", tableLayout: "fixed" },
        "& .ProseMirror td, & .ProseMirror th": { border: "1px solid #D1D5DB", padding: "4px 8px", minWidth: "40px", position: "relative" },
        "& .ProseMirror th": { background: "#F3F4F6", fontWeight: 600 },
        "& .ProseMirror hr": { border: "none", borderTop: "1px solid #D1D5DB", margin: "10px 0" },
      }}>
        <EditorContent editor={editor} />
      </Box>

      <Popover open={Boolean(anchor) && !mapField} anchorEl={anchor} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}>
        <Box sx={{ p: 1.5, width: 320 }}>
          <Autocomplete
            options={[...fields].sort((a, b) =>
              Number(!!b.is_anchor) - Number(!!a.is_anchor)
              || a.entity.localeCompare(b.entity) || a.label.localeCompare(b.label))}
            groupBy={(o) => o.entity}
            getOptionLabel={(o) => o.label}
            onChange={(_, v) => v && onFieldPicked(v)}
            renderInput={(p) => (
              <TextField {...p} autoFocus size="small"
                label={replacing ? "Replace selection with field" : "Insert field"}
                placeholder="Search fields…" />
            )}
            renderOption={(props, o) => (
              <li {...props} key={o.ref}>
                <Box>
                  <Box sx={{ fontSize: "0.85rem" }}>{o.label}</Box>
                  <Box sx={{ fontSize: "0.7rem", color: "#9CA3AF", fontFamily: "ui-monospace, monospace" }}>{o.ref}</Box>
                  {o.description && (
                    <Box sx={{ fontSize: "0.7rem", color: "#6B7280" }}>{o.description}</Box>
                  )}
                  {!!o.sample_values?.length && (
                    <Box sx={{ fontSize: "0.7rem", color: "#6B7280", fontStyle: "italic" }}>
                      e.g. {o.sample_values.join(", ")}
                    </Box>
                  )}
                </Box>
              </li>
            )}
          />
        </Box>
      </Popover>
      <ValueMapPopover anchorEl={anchor} field={mapField}
        onClose={() => setMapField(null)} onInsert={insertToken} />
    </Box>
  );
}
