// TS mirror of app/domain/semantic.py GlossaryTerm.
export interface GlossaryTerm {
  term: string;
  aliases?: string[];
  definition: string;
  ref?: string | null;       // metric.<key> or <entity>.<field>
  category?: string | null;  // payroll | workforce | leave | ...
  source?: string;           // seed | custom
}
