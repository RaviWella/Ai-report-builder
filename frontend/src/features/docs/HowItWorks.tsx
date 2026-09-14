// In-app technical reference for admins / tech leads. A single scrollable page
// covering the whole system: architecture, request lifecycle, how a report is
// built, the AI's role, the semantic layer (what it is, how it's built & kept
// current), the query engine, custom fields, runtime filters, multi-tenancy,
// async, security and the tech stack. Pure presentational — no data fetching.
import { type ReactNode } from "react";
import { Box, Card, CardContent, Chip, Divider, Stack, Typography } from "@mui/material";
import {
  AutoAwesomeOutlined, StorageOutlined, SecurityOutlined, BoltOutlined, SchemaOutlined,
  MenuBookOutlined, FunctionsOutlined, HistoryToggleOffOutlined, TranslateOutlined,
  AccountTreeOutlined, GroupWorkOutlined, DescriptionOutlined, LayersOutlined,
} from "@mui/icons-material";

const TEAL = "#007499";
const MONO = { fontFamily: "ui-monospace, Menlo, monospace", fontSize: "0.78rem" };

function Section({ icon, title, subtitle, children }: { icon: ReactNode; title: string; subtitle?: string; children: ReactNode }) {
  return (
    <Card sx={{ mb: 2.5 }}>
      <CardContent>
        <Stack direction="row" spacing={1.25} alignItems="center" sx={{ mb: subtitle ? 0.25 : 1.5 }}>
          <Box sx={{ color: TEAL, display: "flex" }}>{icon}</Box>
          <Typography variant="h6">{title}</Typography>
        </Stack>
        {subtitle && <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{subtitle}</Typography>}
        {children}
      </CardContent>
    </Card>
  );
}

// ── Diagram primitives ──────────────────────────────────────────────────
function Layer({ title, items, tone = "plain" }: { title: string; items: string[]; tone?: "accent" | "plain" | "data" }) {
  const bg = tone === "accent" ? "#EAF4F7" : tone === "data" ? "#FFF7ED" : "#F9FAFB";
  const bd = tone === "accent" ? TEAL : tone === "data" ? "#F59E0B" : "#E5E7EB";
  return (
    <Box sx={{ border: `1.5px solid ${bd}`, bgcolor: bg, borderRadius: 2, px: 2, py: 1.1, width: "100%" }}>
      <Typography sx={{ fontWeight: 700, fontSize: "0.82rem", mb: 0.5 }}>{title}</Typography>
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
        {items.map((it) => <Chip key={it} label={it} size="small" variant="outlined" sx={{ bgcolor: "#fff" }} />)}
      </Stack>
    </Box>
  );
}
function DNode({ title, sub }: { title: string; sub: string }) {
  return (
    <Box sx={{ border: `1.5px solid ${TEAL}`, bgcolor: "#fff", borderRadius: 2, px: 1.25, py: 1, textAlign: "center" }}>
      <Typography sx={{ fontWeight: 700, fontSize: "0.78rem", color: TEAL }}>{title}</Typography>
      <Typography sx={{ fontSize: "0.66rem", color: "#6B7280", mt: 0.25 }}>{sub}</Typography>
    </Box>
  );
}
const Arrow = ({ label }: { label: string }) => (
  <Stack alignItems="center" sx={{ py: 0.25 }}>
    <Typography sx={{ fontSize: "0.66rem", color: "#6B7280" }}>{label}</Typography>
    <Typography sx={{ color: "#9CA3AF", lineHeight: 1 }}>▼</Typography>
  </Stack>
);

// A full-width numbered tier in a vertical flow (used for the governed-stack diagram).
function FlowBox({ n, title, detail, tone = "plain", tag }: {
  n: number; title: string; detail: ReactNode; tone?: "accent" | "plain" | "data" | "new"; tag?: string;
}) {
  const map = {
    accent: { bg: "#EAF4F7", bd: TEAL }, plain: { bg: "#F9FAFB", bd: "#9CA3AF" },
    data: { bg: "#FFF7ED", bd: "#F59E0B" }, new: { bg: "#F0FDF4", bd: "#16A34A" },
  }[tone];
  return (
    <Box sx={{ border: `1.5px solid ${map.bd}`, bgcolor: map.bg, borderRadius: 2, px: 1.5, py: 1, width: "100%", display: "flex", alignItems: "center", gap: 1.25 }}>
      <Box sx={{ flexShrink: 0, width: 24, height: 24, borderRadius: "50%", bgcolor: map.bd, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.72rem", fontWeight: 700 }}>{n}</Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" spacing={0.75} alignItems="center">
          <Typography sx={{ fontWeight: 700, fontSize: "0.82rem" }}>{title}</Typography>
          {tag && <Chip label={tag} size="small" sx={{ height: 17, fontSize: "0.58rem", fontWeight: 700, bgcolor: tag === "NEW" ? "#16A34A" : "#0EA5E9", color: "#fff", "& .MuiChip-label": { px: 0.75 } }} />}
        </Stack>
        <Typography sx={{ fontSize: "0.72rem", color: "#4B5563" }}>{detail}</Typography>
      </Box>
    </Box>
  );
}
const FArrow = () => <Typography sx={{ color: "#9CA3AF", lineHeight: 1, py: 0.15 }}>▼</Typography>;

// A deep-dive entry for one layer: what it is, the problem that forced it, the
// tech, and an optional code/diagram snippet.
function DeepLayer({ n, name, tag, what, why, tech, code }: {
  n: number; name: string; tag?: string; what: ReactNode; why: ReactNode; tech: string[]; code?: string;
}) {
  return (
    <Box sx={{ borderLeft: `3px solid ${TEAL}`, pl: 1.5, py: 0.4, mb: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.4 }}>
        <Box sx={{ flexShrink: 0, width: 22, height: 22, borderRadius: "50%", bgcolor: TEAL, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem", fontWeight: 700 }}>{n}</Box>
        <Typography sx={{ fontWeight: 700, fontSize: "0.92rem" }}>{name}</Typography>
        {tag && <Chip label={tag} size="small" sx={{ height: 17, fontSize: "0.58rem", fontWeight: 700, bgcolor: tag === "NEW" ? "#16A34A" : "#0EA5E9", color: "#fff", "& .MuiChip-label": { px: 0.75 } }} />}
      </Stack>
      <Typography variant="body2" sx={{ mb: 0.4 }}>{what}</Typography>
      <Typography variant="body2" sx={{ mb: 0.6 }}><b style={{ color: "#B45309" }}>Why / the problem:</b> {why}</Typography>
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: code ? 0.75 : 0 }}>
        {tech.map((t) => <Chip key={t} label={t} size="small" sx={{ height: 20, bgcolor: "#EAF4F7", color: TEAL, fontWeight: 600, fontSize: "0.66rem" }} />)}
      </Stack>
      {code && (
        <Box component="pre" sx={{ ...MONO, bgcolor: "#111827", color: "#E5E7EB", borderRadius: 1.5, p: 1.1, m: 0, whiteSpace: "pre", overflowX: "auto", fontSize: "0.72rem", lineHeight: 1.5 }}>{code}</Box>
      )}
    </Box>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ mb: 1.4 }}>
      <Box sx={{ flexShrink: 0, width: 26, height: 26, borderRadius: "50%", bgcolor: TEAL, color: "#fff",
        display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.8rem", fontWeight: 700 }}>{n}</Box>
      <Box>
        <Typography sx={{ fontWeight: 600, fontSize: "0.9rem" }}>{title}</Typography>
        <Typography variant="body2" color="text.secondary">{children}</Typography>
      </Box>
    </Stack>
  );
}

function Mini({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 2, p: 1.5, height: "100%" }}>
      <Typography sx={{ fontWeight: 700, fontSize: "0.83rem", mb: 0.25 }}>{title}</Typography>
      <Typography variant="body2" color="text.secondary">{children}</Typography>
    </Box>
  );
}
function Grid2({ children }: { children: ReactNode }) {
  return <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5 }}>{children}</Box>;
}
const Code = ({ children }: { children: ReactNode }) => <Box component="code" sx={{ ...MONO, color: "#111827" }}>{children}</Box>;

function MapRow({ term, refKey, phys }: { term: string; refKey: string; phys: string }) {
  const arrow = <Typography sx={{ color: "#9CA3AF", textAlign: "center" }}>→</Typography>;
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "1.1fr 24px 1fr 24px 1.5fr", alignItems: "center", gap: 0.5, py: 0.6 }}>
      <Chip label={term} size="small" sx={{ bgcolor: "#EAF4F7", color: TEAL, fontWeight: 600, justifySelf: "start" }} />
      {arrow}
      <Box component="code" sx={{ ...MONO, color: "#111827" }}>{refKey}</Box>
      {arrow}
      <Box component="span" sx={{ ...MONO, color: "#9CA3AF" }}>{phys}</Box>
    </Box>
  );
}
function TechGroup({ title, items }: { title: string; items: string[] }) {
  return (
    <Box sx={{ mb: 1.25 }}>
      <Typography sx={{ fontSize: "0.72rem", fontWeight: 700, color: "#6B7280", textTransform: "uppercase", mb: 0.5 }}>{title}</Typography>
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
        {items.map((t) => <Chip key={t} label={t} size="small" sx={{ bgcolor: "#EAF4F7", color: TEAL, fontWeight: 600 }} />)}
      </Stack>
    </Box>
  );
}

export function HowItWorks() {
  return (
    <Box sx={{ maxWidth: 940 }}>
      <Typography variant="h4" sx={{ mb: 0.5 }}>How it works — technical overview</Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        A self-service report builder that lets non-technical HR users design, preview and publish
        reports from the HR datamart — AI maps intent to data, a semantic layer translates business
        terms to columns, and every query runs on a strictly read-only, per-tenant, governed path. No SQL.
        On top of the catalogue sit three governed tiers — <b>metrics</b> (one definition per number),
        a <b>glossary</b> (business words → that number) and a <b>deterministic resolver</b> — and under it a
        <b> snapshot-keyed result cache</b>. See <i>“The layer stack”</i> below for the full flow, layer by layer.
      </Typography>

      {/* ── The core idea (Mint HR OS concept) ─────────────────────────── */}
      <Section icon={<AutoAwesomeOutlined />} title="The core idea — understand meaning once, reuse forever"
        subtitle="Natural language is infinite; HR concepts are finite. We interpret a question ONCE into a small business specification, then COMPILE it deterministically. The language model runs only at the meaning step (and only when the deterministic resolver can’t) — it never writes SQL.">
        <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 0.75, mb: 2 }}>
          {[
            ["Question", "plain language"],
            ["Understand", "the 5 blocks"],
            ["Semantic layer", "terms → columns"],
            ["Business spec", "reusable JSON, no SQL"],
            ["Compiler", "assembles safe SQL"],
            ["Database", "read-only"],
          ].map(([t, s], i) => (
            <Stack key={t} direction="row" spacing={0.75} alignItems="center">
              {i > 0 && <Typography sx={{ color: "#9CA3AF" }}>→</Typography>}
              <DNode title={t} sub={s} />
            </Stack>
          ))}
        </Box>
        <Box sx={{ mb: 2 }}>
          <Layer tone="accent" title="Every HR question decomposes into five blocks"
            items={["Subject — entity", "Measure — what’s aggregated", "Grouping — the axis", "Filter — the condition", "Time — the period"]} />
        </Box>
        <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", mb: 1 }}>
          What makes the same question always give the same answer
        </Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.25 }}>
          <Mini title="Canonical-intent store (learn once)">
            A resolved phrasing is saved and <b>replayed</b> — any wording that normalises the same
            returns the same spec. An admin can <b>certify</b> it as the approved answer. The system
            learns; it never re-derives.
          </Mini>
          <Mini title="Deterministic concept-lock (route the same way)">
            Field matching is reproducible (governed metric first, then catalogue order) and
            <b> entity-scoped</b> — “basic salary” resolves to the same column every time, in the
            report’s own entity (no accidental joins).
          </Mini>
          <Mini title="Time block (resolved at run time)">
            “this month”, “YTD”, “last 12 months” are stored <b>symbolically</b> and resolved to the
            current period when the report runs — a saved report never goes stale.
          </Mini>
          <Mini title="Conversational Q&A (about the result)">
            Follow-ups like “total of above”, “which is highest” are computed straight from the
            shown result (no model); open-ended ones (“explain this”, “what %…”) use the configured
            model, grounded only on that table.
          </Mini>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.75 }}>
          This is <b>not</b> dynamic text-to-SQL (an AI re-writing SQL every time — non-deterministic,
          hard to govern) and <b>not</b> a library of frozen SQL (brittle). New combinations compile on
          demand from a governed semantic layer, and a <b>coverage audit</b> flags any mapped field whose
          datamart column is empty — so a correct mapping over missing data is caught, not shipped.
        </Typography>
      </Section>

      {/* ── Architecture / component diagram ───────────────────────────── */}
      <Section icon={<SchemaOutlined />} title="Architecture"
        subtitle="Browser → API → four engines → metadata DB + read-only datamart, with an async sidecar.">
        <Stack alignItems="center" spacing={0}>
          <Layer tone="accent" title="① Browser — React SPA" items={["Builder", "Viewer", "Admin / AI settings"]} />
          <Arrow label="HTTPS · JWT (tenant + role)" />
          <Layer tone="accent" title="② API — FastAPI" items={["AuthN/Z + tenant guard", "Report & template services", "Excel ingestion", "Audit log"]} />
          <Arrow label="orchestrates the four engines" />
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" }, gap: 1, width: "100%" }}>
            <DNode title="AI Adapter" sub="NL→spec · mapping · metadata-only" />
            <DNode title="Semantic Layer" sub="refs ↔ columns · per-tenant" />
            <DNode title="Query Engine" sub="spec → safe SQL" />
            <DNode title="Renderers" sub="Excel · PDF" />
          </Box>
          <Arrow label="parameterised · READ-ONLY SELECT" />
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1, width: "100%" }}>
            <Layer title="Metadata DB — PostgreSQL" items={["templates · versions", "semantic catalogue", "audit · encrypted AI keys"]} />
            <Layer tone="data" title="Datamart — hrm_wh_{tenant} (read replica)" items={["schemas hr · hr_semantic", "vw_data_dictionary", "employee · payroll · paysheet · leave · attendance"]} />
          </Box>
          <Box sx={{ width: "100%", mt: 1 }}>
            <Layer title="Redis — result cache + Celery sidecar" items={["result cache (snapshot-keyed)", "worker: async exports", "beat: scheduled reports", "beat: nightly semantic refresh"]} />
          </Box>
        </Stack>
      </Section>

      {/* ── The layer stack — deep dive (datamart → up) ────────────────── */}
      <Section icon={<LayersOutlined />} title="The layer stack — datamart → up, and why each layer exists"
        subtitle="Read top-down, starting at the source. Each tier turns raw warehouse data a little more business-friendly, safe, governed and fast. For every layer: what it is, the problem that forced it, and the tech.">
        <Stack alignItems="center" spacing={0} sx={{ mb: 2 }}>
          <FlowBox n={1} tone="data" title="Datamart — per-tenant read replica (VPN)"
            detail={<>Where every value physically lives. Flaky and expensive — a cache hit (next tier) <b>skips it entirely</b>.</>} />
          <FArrow />
          <FlowBox n={2} tone="new" tag="NEW" title="Result cache — snapshot-keyed, single-flight"
            detail={<>Checked before the datamart. <b>Hit → rows without touching it.</b> Key embeds the data snapshot, so a refresh makes stale entries unreachable.</>} />
          <FArrow />
          <FlowBox n={3} tone="plain" title="Query Engine — spec → safe SQL"
            detail={<>The parameterised, read-only <Code>SELECT</Code> that produced the rows. The engine writes the SQL, never the AI.</>} />
          <FArrow />
          <FlowBox n={4} tone="accent" title="Semantic catalogue — refs ↔ physical"
            detail={<>Maps each <Code>ref</Code> to <Code>schema.table.column</Code> + joins, and a metric to its field(s). Per-tenant, versioned, pinned.</>} />
          <FArrow />
          <FlowBox n={5} tone="accent" tag="UPDATED" title="Deterministic resolver → spec"
            detail={<>Turns the request into a spec with zero LLM — matching field + metric labels, aliases and glossary synonyms. LLM is only a fallback.</>} />
          <FArrow />
          <FlowBox n={6} tone="new" tag="NEW" title="Metrics tier — one governed definition"
            detail={<><Code>metric.&lt;key&gt;</Code> = the single agreed meaning of a number (aggregate / count / formula), validated when defined.</>} />
          <FArrow />
          <FlowBox n={7} tone="new" tag="NEW" title="Glossary — business words → governed ref"
            detail={<>A per-tenant term resolves a synonym to the governed ref: <Code>“in-hand salary” → metric.total_net</Code>.</>} />
          <FArrow />
          <Box sx={{ bgcolor: "#EAF4F7", border: `1.5px solid ${TEAL}`, borderRadius: 2, px: 1.5, py: 0.9, width: "100%", textAlign: "center" }}>
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: TEAL, textTransform: "uppercase", mb: 0.25 }}>Delivered to the user</Typography>
            <Typography variant="body2">“<b>in-hand salary</b> by branch” — answered, no SQL written by hand</Typography>
          </Box>
        </Stack>

        <Divider sx={{ my: 1.5 }} />
        <Typography sx={{ fontWeight: 700, fontSize: "0.9rem", mb: 1.25 }}>Why each layer exists — with the code</Typography>

        <DeepLayer n={0} name="Datamart — the foundation"
          what={<>Each client (tenant) has its own warehouse DB <Code>hrm_wh_&#123;tenant&#125;</Code> — a read replica reached over a VPN, with marts for Employee, Payroll, Leave, Attendance and dynamic pay items.</>}
          why={<>Physical names are cryptic (<Code>net_amount</Code>), pay items differ per client, the VPN is flaky, and it’s read-only. Everything above exists to tame those four facts.</>}
          tech={["PostgreSQL (per-tenant DB)", "SQLAlchemy pool", "WireGuard VPN"]} />

        <DeepLayer n={1} name="Read-only access guards" what={<>Three independent layers force every datamart query to be read-only.</>}
          why={<>It’s a SaaS holding client HR data — an app bug or an AI slip must never be able to write or delete. Defense in depth: if one layer fails, the others still catch it.</>}
          tech={["PostgreSQL read-only role", "read-only transaction", "assert_select_only guard"]}
          code={`def assert_select_only(sql: str) -> None:
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        raise GuardError("Only SELECT is allowed")
    # INSERT / UPDATE / DELETE / DROP / ';' (multi-stmt)  -> rejected`} />

        <DeepLayer n={2} name="Semantic layer — the heart" what={<>A per-tenant, versioned JSON map from a business <Code>ref</Code> (<Code>payroll.net</Code>) to a physical <Code>schema.table.column</Code> + joins + type/role/PII. It’s metadata, not data — and not a SQL view.</>}
          why={<>Users think “Net Salary”; the warehouse stores <Code>net_amount</Code>. Pay items differ per client, so it can’t be hand-coded — it’s <b>auto-introspected</b> per tenant. And the AI must never see physical names, so it only ever sees the <Code>ref</Code> side.</>}
          tech={["Pydantic v2", "JSONB in PostgreSQL", "SQLAlchemy introspection"]}
          code={`SemanticField(
    ref="payroll.net",          # AI/spec sees ONLY this
    label="Net Salary",
    type=DECIMAL, role=MEASURE,
    physical=PhysicalColumn(    # hidden from AI + user
        table="vw_payroll_summary", column="net_amount"),
    pii=True,
)`} />

        <DeepLayer n={3} name="Query Engine — spec → safe SQL" what={<>User choices become a JSON <b>spec</b> (refs, filters, joins, groups). The engine compiles it to one parameterised, read-only <Code>SELECT</Code>.</>}
          why={<>If the AI wrote SQL directly: injection risk + wrong SQL. So the AI only emits a <i>spec</i>; the engine deterministically builds safe SQL with filter values <b>bound as parameters</b>, never concatenated. (A period-grain bug that duplicated rows was fixed here with period-aligned joins.)</>}
          tech={["SQLAlchemy Core", "guards", "AST evaluator (no eval)"]}
          code={`spec:  { fields: ["payroll.net"],
         filters: [{ ref:"payroll.period", op:"eq", param:"period" }] }
   |  Query Engine
SQL:   SELECT net_amount FROM hr_semantic.vw_payroll_summary
       WHERE period_label = :period      -- bound, not concatenated`} />

        <DeepLayer n={4} name="Metrics tier — one governed definition" tag="NEW"
          what={<>A named <Code>metric.&lt;key&gt;</Code> layer over the fields — the single definition of a business number (aggregate / count / formula).</>}
          why={<>“Headcount” was being re-derived 10 different ways across reports (<Code>count(*)</Code> vs <Code>count(distinct)</Code>). Defining it once, <b>validated on define</b> (a bad ref/formula is rejected up front), means it’s identical everywhere.</>}
          tech={["Pydantic (MetricDef)", "JSONB storage", "validate-on-compile"]}
          code={`MetricDef(key="total_net", label="Total Net Pay",
          kind="aggregate", agg=SUM, ref="payroll.net")
# referenced as:  metric.total_net
# formula kind:   expression="metric.total_gross - metric.total_deductions"`} />

        <DeepLayer n={5} name="Glossary tier — business vocabulary" tag="NEW"
          what={<>Per-tenant <b>term → definition → governed ref</b>. Feeds the resolver as synonyms and documents the layer.</>}
          why={<>A user asking for “in-hand salary” names neither a field nor a metric, so the system used to guess. The glossary maps the phrase onto <Code>metric.total_net</Code> — grounded, and consistent for everyone on the tenant.</>}
          tech={["Pydantic (GlossaryTerm)", "JSONB storage", "validate-on-define"]}
          code={`GlossaryTerm(term="Take-home Pay", ref="metric.total_net",
             aliases=["in-hand salary", "net pay"],
             definition="Net amount after all deductions.")`} />

        <DeepLayer n={6} name="Deterministic resolver — NL without the LLM" tag="UPDATED"
          what={<>Common requests become a spec by matching field + metric labels, aliases and glossary synonyms — <b>zero LLM calls</b>. The LLM is only a fallback for the unusual.</>}
          why={<>Sending every request to an LLM is costly, slow and non-deterministic. A deterministic path for the common shapes is cheaper, faster, reproducible and auditable.</>}
          tech={["Plain Python (regex + containment)", "no ML / no LLM"]}
          code={`resolve_intent("in-hand salary by department", catalog)
# -> DataSpec(fields=[employee.department, metric.total_net])
#    source = "deterministic"        (LLM calls = 0)
# tiered: if confidence >= 0.6 serve it, else fall back to the LLM`} />

        <DeepLayer n={7} name="AI adapter — the LLM, as a fallback"
          what={<>For requests the resolver can’t handle, plus Excel-heading mapping and “describe a custom field”. Provider-agnostic.</>}
          why={<>Flexibility for open-ended requests — but the AI sees <b>metadata only</b> (no PII, no data rows, no physical names) and never writes SQL. It returns a <i>proposal</i> that’s validated and editable before anything runs.</>}
          tech={["Anthropic Claude / self-hosted vLLM", "Pydantic structured output", "Fernet-encrypted keys"]} />

        <DeepLayer n={8} name="Result cache — Redis, snapshot-keyed" tag="NEW"
          what={<>Caches the result so an identical run is served from Redis instead of the datamart.</>}
          why={<>Every run otherwise hits the flaky VPN live; two users on the same report = two round-trips. <b>Correct by construction:</b> the data snapshot is part of the key, so a refresh makes old entries unreachable — stale is never served. Single-flight stops a popular report stampeding the replica.</>}
          tech={["Redis (shared, multi-pod)", "pickle+zlib", "SET NX lock", "fail-safe"]}
          code={`key = sha256(f"{tenant} | {compiled_sql_hash} | {params} | {snapshot_ref}")
#  hit  -> rows from Redis (datamart untouched)
#  miss -> single-flight lock -> execute -> cache.set(key, result)
#  snapshot changes -> key changes -> old (stale) entry unreachable`} />

        <DeepLayer n={9} name="Governance, lineage & multi-tenancy" what={<>Every run records <Code>compiled_sql_hash</Code>, a <Code>result_checksum</Code> and the data snapshot (<Code>report_runs</Code>); data-quality gates and an audit log wrap it. Identity is a tenant-scoped JWT.</>}
          why={<>For SaaS HR data you must prove “which data, when, and was it valid”, and one client must never see another’s. Tenant scope + lineage + audit make every result reproducible and accountable.</>}
          tech={["SHA-256 lineage", "report_runs / validation tables", "FastAPI + Authlib JWT", "RBAC"]} />
      </Section>

      {/* ── Request lifecycle ──────────────────────────────────────────── */}
      <Section icon={<AccountTreeOutlined />} title="Request lifecycle — one ‘Run’"
        subtitle="What happens between clicking Run and seeing rows.">
        <Step n={1} title="API authenticates & scopes the tenant">
          JWT verified → tenant + role resolved. Every downstream call is bound to that tenant; required
          runtime params (e.g. payroll period) are validated before anything runs.
        </Step>
        <Step n={2} title="Resolve the pinned spec & catalogue">
          The published report’s immutable spec is loaded with the exact semantic-catalogue version it was
          pinned to — so behaviour never drifts when the layer is later refreshed.
        </Step>
        <Step n={3} title="Query Engine compiles the spec">
          Each <Code>ref</Code> is resolved to its physical schema/table/column via the catalogue; joins,
          filters (bound as parameters), groupings and calculated fields become one SQLAlchemy Core SELECT.
        </Step>
        <Step n={4} title="Result cache check (snapshot-keyed)">
          The cache key is <Code>tenant · compiled SQL hash · params · datamart snapshot</Code>. A <b>hit returns
          the rows immediately — the datamart is never touched</b>. On a miss, a single-flight lock lets one
          caller compute while duplicates wait, so a popular report can’t stampede the replica.
        </Step>
        <Step n={5} title="Guards + read-only execution (on a miss)">
          <Code>assert_select_only</Code> rejects anything but SELECT; the query is wrapped in a read-only
          transaction on a read-only DB user, with a row limit and statement timeout, against the tenant’s
          datamart. The result is then cached for the next identical run.
        </Step>
        <Step n={6} title="Shape & return / render">
          Rows are returned to the Viewer (paginated client-side) or handed to the Excel / PDF renderer for a
          branded, full-data export. The run is written to the audit log (with a <Code>cached</Code> flag).
        </Step>
      </Section>

      {/* ── How a report is born ───────────────────────────────────────── */}
      <Section icon={<BoltOutlined />} title="How a report is built — step by step">
        <Step n={1} title="Describe what you want">
          Upload a sample Excel, describe it in plain words, or pick fields. Uploaded sheets are parsed
          locally — only the <i>column headings</i> are read, never the data rows.
        </Step>
        <Step n={2} title="Map headings → semantic fields">
          Local fuzzy-match first; the AI handles the ambiguous remainder. The AI only sees field <i>metadata</i>.
        </Step>
        <Step n={3} title="Build a validated query spec (not SQL)">
          Your choices become a JSON <b>spec</b>: fields, filters, groupings, calculated columns, sort, runtime
          params — referencing business <Code>refs</Code>, not tables.
        </Step>
        <Step n={4} title="Compile to safe SQL → preview">
          The engine emits a parameterised SELECT and you preview with real data.
        </Step>
        <Step n={5} title="Name, choose a module, publish">
          Publishing snapshots an <b>immutable version</b>, pinned to the catalogue version it was built against.
        </Step>
        <Step n={6} title="Run & export in the Viewer">
          End users set runtime filters, Run, and download branded Excel / PDF.
        </Step>
      </Section>

      {/* ── Documents (one page per record) ────────────────────────────── */}
      <Section icon={<DescriptionOutlined />} title="Documents — one page per record"
        subtitle="The same per-record data, rendered as a formatted document (payslip, statement, certificate) instead of a table of rows.">
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          A template has a <b>kind</b> — a <b>table report</b> (records as rows) or a <b>document</b> (one page
          per record) — plus the output formats it allows (<Code>view</Code> / <Code>excel</Code> / <Code>pdf</Code>).
          Both share the same data layer, semantic refs, joins and the common Viewer; only the rendering differs.
          “Document” is <b>generic, not an HR payslip</b> — sections carry whatever titles the uploaded layout used.
        </Typography>
        <Grid2>
          <Mini title="Built from a layout">Upload a one-page layout; we detect its <b>sections</b> (any title), identity fields, totals and footer — only labels are read, never values.</Mini>
          <Mini title="Lines → fields">Each line is fuzzy/AI-mapped to a semantic field (money lines must be <b>measures</b>); you review and fix it in the builder.</Mini>
          <Mini title="Detail blocks">Optional <b>one→many</b> blocks per record (e.g. an employee’s bank accounts) supplied by a named <Code>provider</Code> — add a block type by registering a provider, no renderer change.</Mini>
          <Mini title="Common Generate">Stored as a report_template (<Code>kind: document</Code>) with a derived per-record query; the Viewer shows the same period / record filters and exports one PDF, a page per record.</Mini>
        </Grid2>
      </Section>

      {/* ── Reading the Excel sample ───────────────────────────────────── */}
      <Section icon={<MenuBookOutlined />} title="Reading your Excel sample"
        subtitle="Upload a sheet that looks like the report you want — we read its layout, not its data.">
        <Step n={1} title="Only headings are read — never the data">
          Parsed server-side with <b>pandas / openpyxl</b>; every data row is stripped first. We keep only the
          column headings and an inferred type.
        </Step>
        <Step n={2} title="The header row is auto-detected">
          Title rows, blank rows, even two-row / merged section headers (an “EARNINGS” band over several
          allowance columns) are handled — we pick the <b>band that yields the most real column names</b>.
        </Step>
        <Step n={3} title="Headings matched — locally first, AI for the rest">
          Each heading is normalised and fuzzy-matched to the semantic fields’ labels. Exact / near matches
          resolve <b>instantly with no AI</b> (even through merged-section prefixes). Only ambiguous headings go
          to the AI in small batches; if the AI is unavailable the best local guess is used — never stalls or overflows.
        </Step>
        <Step n={4} title="You confirm — unmatched get logic or are skipped">
          Matched columns are pre-filled to confirm; anything with no direct field can get a formula / banding
          rule or be skipped.
        </Step>
      </Section>

      {/* ── Where AI helps ─────────────────────────────────────────────── */}
      <Section icon={<AutoAwesomeOutlined />} title="Where the AI helps (and where it doesn’t)"
        subtitle="AI assists three authoring tasks — always on metadata only, never on PII, data or SQL.">
        <Grid2>
          <Mini title="① Natural language → spec">
            “Headcount by department for permanent staff” → a validated query spec. The model is given the field
            catalogue and returns structured JSON that is checked against the Pydantic schema before use.
          </Mini>
          <Mini title="② Excel heading → field mapping">
            For headings local matching can’t resolve confidently, the AI proposes the best semantic field.
            Runs in small batches; output is JSON-validated with truncation recovery.
          </Mini>
          <Mini title="③ Describe a custom field">
            “Under 20 / 20-30 / 30+ from age” → a banding rule (CASE-WHEN), expressed structurally — not raw SQL.
          </Mini>
          <Mini title="Provider-agnostic & guarded">
            Anthropic <b>or</b> a self-hosted vLLM / proxy, swappable per tenant. Token budget is computed to fit
            small context windows; the AI <b>never</b> writes SQL, sees PII, or sees data rows.
          </Mini>
        </Grid2>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.25 }}>
          The engine — not the AI — writes the SQL. The AI only produces a <i>proposal</i> that is validated,
          shown to you, and editable before anything runs.
        </Typography>
      </Section>

      {/* ── Why a semantic layer ───────────────────────────────────────── */}
      <Section icon={<TranslateOutlined />} title="Why a semantic layer — the heart of the system"
        subtitle="It translates business terms ↔ physical datamart columns: a per-tenant, versioned map.">
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          The datamart stores data under cryptic, per-tenant physical names; HR users think in business terms.
          The semantic layer is the translation map in between — users pick “Net Salary”, while the physical
          tables, joins and raw columns stay hidden.
        </Typography>
        <Box sx={{ bgcolor: "#EAF4F7", border: `1px solid ${TEAL}55`, borderRadius: 2, px: 1.5, py: 1, mb: 1.75 }}>
          <Typography variant="body2">
            <b>It’s metadata, not data — and not a SQL view.</b> The layer is a <b>versioned JSON mapping</b>
            (business <Code>ref</Code> → physical <Code>schema.table.column</Code> + joins + type/role/PII),
            <b> defined as Pydantic models</b> and <b>stored as JSONB in PostgreSQL</b>. It holds <b>no rows</b>:
            a Python service builds it by introspecting the datamart, and the Query Engine reads it to compile
            SQL. So it’s both code (the shape) and data (the saved catalogue) — but never a view over the data.
          </Typography>
        </Box>
        <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 2, p: 1.5, mb: 1.75, overflowX: "auto" }}>
          <Box sx={{ display: "grid", gridTemplateColumns: "1.1fr 24px 1fr 24px 1.5fr", gap: 0.5, pb: 0.5, borderBottom: "1px solid #F3F4F6" }}>
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: "#6B7280", textTransform: "uppercase" }}>User sees</Typography>
            <span />
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: "#6B7280", textTransform: "uppercase" }}>Ref (AI/spec sees)</Typography>
            <span />
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: "#6B7280", textTransform: "uppercase" }}>Physical column (hidden)</Typography>
          </Box>
          <MapRow term="Net Salary" refKey="payroll.net" phys="vw_payroll_summary.net_amount" />
          <MapRow term="Blend Allowance" refKey="paysheet.blend" phys="…paysheet_dynamic.addition_blend_allowance" />
          <MapRow term="Pay Period" refKey="payroll.period" phys="vw_payroll_summary.period_label" />
        </Box>
        <Grid2>
          <Mini title="No SQL for users">Pick friendly fields; the engine writes the safe SQL.</Mini>
          <Mini title="AI privacy">The AI sees field metadata only — no raw schema, no PII, no data.</Mini>
          <Mini title="Per-tenant & dynamic">Each client’s own pay items are auto-introspected into their own map.</Mini>
          <Mini title="Stable reports">Versioned & pinned — a schema change never breaks a published report.</Mini>
        </Grid2>
        <Divider sx={{ my: 1.75 }} />
        <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", mb: 0.5 }}>Built with</Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          Hand-built so it can be <b>per-tenant, dynamic, AI-native and governed</b>, with no extra service to run:
        </Typography>
        <Grid2>
          <Mini title="Pydantic v2">Defines & validates the catalogue — entities, fields, joins, types, PII.</Mini>
          <Mini title="SQLAlchemy Core">Introspects the datamart (reads the dictionary) and compiles refs → parameterised SQL.</Mini>
          <Mini title="PostgreSQL">Stores each tenant’s catalogue as a versioned JSON document.</Mini>
          <Mini title="Plain Python service">Seeds the core, auto-introspects pay items, handles version pinning.</Mini>
        </Grid2>
      </Section>

      {/* ── Semantic layer & schema ────────────────────────────────────── */}
      <Section icon={<StorageOutlined />} title="Semantic layer & datamart schema">
        <Typography variant="body2" sx={{ mb: 1 }}>
          The datamart is <b>per-tenant</b>: database <Code>hrm_wh_&#123;tenant&#125;</Code>, with a curated
          <Code> hr_semantic</Code> schema (clean views) over the raw <Code>hr</Code> marts. That schema includes
          <Code> vw_data_dictionary</Code> — the <b>governed source</b> the semantic layer is built from: each
          field’s description, data type and authoritative <b>PII</b> flag, so the catalogue inherits the
          warehouse team’s governance rather than guessing.
        </Typography>
        <Grid2>
          <Mini title="Entities & joins">Employee, Payroll, Leave, Attendance and the wide <b>Paysheet</b> — joined on the conformed <Code>employee_sk</Code>, so a report can mix a profile with pay items.</Mini>
          <Mini title="Dynamic pay items">Allowances/deductions differ per client. We introspect <Code>mart_horizontal_paysheet_dynamic</Code> (<Code>addition_*</Code> / <Code>deduction_*</Code>) so each tenant’s own items are mappable.</Mini>
          <Mini title="Dimensions vs measures">Each field is typed and roled — measures (amounts) carry their allowed aggregations; dimensions are groupable / filterable.</Mini>
          <Mini title="PII flags">Taken from the dictionary, plus an identifier heuristic — informational, and PII never reaches the AI regardless.</Mini>
        </Grid2>
      </Section>

      {/* ── Semantic lifecycle (how it updates) ────────────────────────── */}
      <Section icon={<HistoryToggleOffOutlined />} title="How the semantic layer is built & stays current"
        subtitle="Zero-touch per tenant; refreshed without ever breaking a published report.">
        <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 2, p: 1.5, mb: 1.5, ...MONO, color: "#374151", overflowX: "auto", whiteSpace: "pre" }}>
{`first use ─► assemble  = curated seed  +  introspect vw_data_dictionary (this tenant)
            └► save as version N  (JSON in metadata DB)

nightly  ─► re-introspect ─► fields changed?  ─yes─► save version N+1
  (Celery beat)                               └─no──► no-op

admin    ─► "Rebuild data fields"  ─► force a new version now

reports  ─► pinned to the version they were published against  (refresh ≠ break)`}
        </Box>
        <Grid2>
          <Mini title="Zero-touch bootstrap">On a new tenant’s first use the catalogue auto-builds (seed + their pay items). Datamart unreachable → seed-only, still works.</Mini>
          <Mini title="Diff-aware refresh">The nightly job bumps the version only when the field set actually changes, so identical runs don’t pile up versions.</Mini>
          <Mini title="Per-tenant by construction">Each tenant is introspected from its own <Code>hrm_wh_&#123;tenant&#125;</Code> — different clients get different pay items.</Mini>
          <Mini title="Pinning = safety">Published reports reference a fixed catalogue version, so adding a new allowance never alters an old report.</Mini>
        </Grid2>
      </Section>

      {/* ── Query engine ───────────────────────────────────────────────── */}
      <Section icon={<AccountTreeOutlined />} title="Query Engine — spec to safe SQL"
        subtitle="The AI produces a spec (intent). The engine — not the AI — produces the SQL.">
        <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", mb: 1 }}>From intent to SQL — a worked example</Typography>
        <Box sx={{ borderRadius: 2, overflow: "hidden", border: "1px solid #E5E7EB", mb: 1.75 }}>
          {/* intent */}
          <Box sx={{ bgcolor: "#F9FAFB", px: 1.5, py: 1 }}>
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: "#6B7280", textTransform: "uppercase", mb: 0.25 }}>① User intent (AI may assist)</Typography>
            <Typography variant="body2">“Net Salary where Pay Period = 2025-07”</Typography>
          </Box>
          {/* spec */}
          <Box sx={{ bgcolor: "#EAF4F7", px: 1.5, py: 1, borderTop: "1px solid #E5E7EB" }}>
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: TEAL, textTransform: "uppercase", mb: 0.25 }}>② Spec — refs only, no SQL (this is all the AI ever emits)</Typography>
            <Box component="pre" sx={{ ...MONO, color: "#0F3D49", m: 0, whiteSpace: "pre-wrap" }}>
{`{ fields:  [ "payroll.net" ],
  filters: [ { ref: "payroll.period", op: "eq", param: "period" } ] }`}
            </Box>
          </Box>
          {/* sql */}
          <Box sx={{ bgcolor: "#111827", px: 1.5, py: 1, borderTop: "1px solid #E5E7EB" }}>
            <Typography sx={{ fontSize: "0.66rem", fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", mb: 0.25 }}>③ Engine builds SQL (SQLAlchemy Core) — value bound as a parameter</Typography>
            <Box component="pre" sx={{ ...MONO, color: "#E5E7EB", m: 0, whiteSpace: "pre-wrap" }}>
{`SELECT net_amount
FROM   hr_semantic.vw_payroll_summary
WHERE  period_label = %(period)s        -- not concatenated`}
            </Box>
            <Box component="pre" sx={{ ...MONO, color: "#7DD3FC", m: 0, mt: 0.5, whiteSpace: "pre-wrap" }}>
{`params: { "period": "2025-07" }`}
            </Box>
          </Box>
          {/* run */}
          <Box sx={{ bgcolor: "#F9FAFB", px: 1.5, py: 0.85, borderTop: "1px solid #E5E7EB" }}>
            <Typography variant="caption" color="text.secondary">
              ④ <Code>assert_select_only</Code> → read-only transaction → execute → rows
            </Typography>
          </Box>
        </Box>
        <Grid2>
          <Mini title="Ref resolution">Every <Code>ref</Code> → schema/table/column via the pinned catalogue. The spec never names a physical table.</Mini>
          <Mini title="One clause per table">A <b>table registry</b> reuses a single clause per physical table, preventing accidental cartesian joins.</Mini>
          <Mini title="Parameterised filters">Filter values bind as SQL parameters (never string-concatenated); incomplete filters are skipped.</Mini>
          <Mini title="Calculated fields">Formulas (arithmetic over refs) and banding (<Code>CASE WHEN</Code> buckets) compile via SQLAlchemy <Code>case()</Code> — structural, never raw SQL.</Mini>
          <Mini title="Validation guards">Refs and joins are validated against the catalogue; unknown refs or unreachable entities are rejected before execution.</Mini>
          <Mini title="Limits & timeout">A hard row limit (and a small preview limit) plus a statement timeout protect the replica.</Mini>
        </Grid2>
      </Section>

      {/* ── Cache correctness callout ──────────────────────────────────── */}
      <Box sx={{ bgcolor: "#F0FDF4", border: "1px solid #16A34A55", borderRadius: 2, px: 1.75, py: 1.25, mb: 2.5 }}>
        <Typography sx={{ fontWeight: 700, fontSize: "0.85rem", mb: 0.5 }}>Why the result cache is correct by construction</Typography>
        <Typography variant="body2">
          The datamart load-watermark (<Code>datamart_snapshot_ref</Code>) is <b>part of the cache key</b>. When the
          warehouse refreshes, the watermark changes → the key changes → old entries become unreachable. So there
          is <b>no explicit invalidation</b> and a <b>stale snapshot is never served</b>; the TTL is only a safety
          net. We cache only when a snapshot exists — without a freshness anchor we don’t risk staleness.
        </Typography>
      </Box>

      {/* ── Custom fields & runtime filters ────────────────────────────── */}
      <Section icon={<FunctionsOutlined />} title="Custom fields & runtime filters">
        <Grid2>
          <Mini title="Formula fields">Arithmetic over existing fields (e.g. <Code>gross − deductions</Code>) — defined in the UI, compiled safely.</Mini>
          <Mini title="Banding fields">Bucket a value into labels (e.g. age → “Under 20 / 20-30 / 30+”) as governed CASE-WHEN rules.</Mini>
          <Mini title="Dynamic runtime filters">Defined per report; the Viewer renders the right control — dropdown / date / date-range / text / number.</Mini>
          <Mini title="Required & smart defaults">A filter can be <b>required</b> (Run is blocked until set); period dropdowns can default to the latest value, with options fetched live.</Mini>
        </Grid2>
      </Section>

      {/* ── Multi-tenancy, async, secrets ──────────────────────────────── */}
      <Section icon={<GroupWorkOutlined />} title="Multi-tenancy, scheduling & secrets">
        <Grid2>
          <Mini title="Tenant isolation">Identity arrives as a JWT; every query and catalogue is scoped to that tenant’s own datamart database.</Mini>
          <Mini title="RBAC">Role checks gate admin actions (e.g. rebuilding the layer) vs. authoring vs. viewing.</Mini>
          <Mini title="Async & scheduled (Celery)">Heavy exports run on a worker; a beat schedule dispatches scheduled reports and the nightly semantic refresh.</Mini>
          <Mini title="Encrypted AI keys">UI-entered provider keys are encrypted at rest (Fernet) per tenant and never returned to the client.</Mini>
        </Grid2>
      </Section>

      {/* ── Security ───────────────────────────────────────────────────── */}
      <Section icon={<SecurityOutlined />} title="Security & governance">
        <Stack spacing={1}>
          <Typography variant="body2"><b>Read-only datamart (3 layers):</b> a read-only DB user · a read-only transaction · and a query guard that allows only SELECT + calculations — never INSERT / UPDATE / DELETE / DDL.</Typography>
          <Typography variant="body2"><b>Tenant isolation:</b> every query is scoped to the caller’s tenant database; identity is a JWT from the parent platform.</Typography>
          <Typography variant="body2"><b>AI privacy:</b> the AI sees field metadata only — no PII, no data rows, no SQL. Uploaded Excel rows are stripped before anything leaves the server.</Typography>
          <Typography variant="body2"><b>Secrets:</b> UI-entered AI keys are Fernet-encrypted; DB / JWT secrets come from the environment, never the repo.</Typography>
          <Typography variant="body2"><b>Auditability:</b> runs, AI interactions and publishes are written to an audit log.</Typography>
        </Stack>
      </Section>

      {/* ── Tech stack ─────────────────────────────────────────────────── */}
      <Section icon={<BoltOutlined />} title="Technology stack">
        <TechGroup title="Frontend" items={["React 19", "TypeScript", "Vite", "MUI v7", "TanStack Query", "Zustand"]} />
        <TechGroup title="Backend" items={["Python 3.13", "FastAPI", "SQLAlchemy Core", "Pydantic v2", "Alembic", "Authlib (JWT)"]} />
        <TechGroup title="Data" items={["PostgreSQL", "Per-tenant datamart", "pandas", "openpyxl", "vw_data_dictionary"]} />
        <TechGroup title="AI" items={["Anthropic Claude", "Self-hosted vLLM / proxy", "Structured-output validation"]} />
        <TechGroup title="Async & infra" items={["Celery", "Redis", "Docker", "Nginx", "WeasyPrint (PDF)"]} />
        <TechGroup title="Security" items={["OAuth2 / JWT", "RBAC", "Fernet encryption", "Read-only guards"]} />
      </Section>

      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
        Every concept above is implemented in this codebase — backend (FastAPI · query engine · semantic layer ·
        AI adapter · renderers · Celery) and frontend (builder · viewer · admin).
      </Typography>
    </Box>
  );
}
