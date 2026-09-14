// Highlight {{semantic.ref}} tokens and leftover Word «MergeField» markers in
// the letter editor so they stay readable (Word often pastes them in near-white).
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

// {{ref}} or {{ref|value=text|...}} (a value map — e.g. {{employee.gender|Male=he|Female=she}}).
const TOKEN_RE = /\{\{\s*[^{}]+?\s*\}\}|«[^»]+»|<<\s*[^>]+?\s*>>/g;

export const MergeTokenHighlight = Extension.create({
  name: "mergeTokenHighlight",
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("mergeTokenHighlight"),
        props: {
          decorations(state) {
            const decos: Decoration[] = [];
            state.doc.descendants((node, pos) => {
              if (!node.isText || !node.text) return;
              for (const m of node.text.matchAll(TOKEN_RE)) {
                if (m.index == null) continue;
                const from = pos + m.index;
                const to = from + m[0].length;
                const wordField = m[0].startsWith("«") || m[0].startsWith("<<");
                decos.push(Decoration.inline(from, to, {
                  class: wordField ? "merge-token merge-token--word" : "merge-token",
                }));
              }
            });
            return DecorationSet.create(state.doc, decos);
          },
        },
      }),
    ];
  },
});
