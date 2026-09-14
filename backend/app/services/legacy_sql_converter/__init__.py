"""Legacy SQL Converter — a purpose-built migration helper.

Turns an old, MySQL-source-DB report query into a plain-language business-
logic document (a "BA doc"), with every legacy table/column/code resolved
against THIS tenant's new datamart. An implementer copies that document into
the existing AI Rule Report chat's requirement input — the same way they'd
paste any other client requirement — to build the governed JSON spec.

Deliberately isolated from `rule_report_ai` (the generic chat + DSL engine):
this tool's entire purpose is bridging the old warehouse to the new one, so
unlike the generic platform, it IS allowed to know about the data
warehouse's internal schema (`core.*`, its dictionary views, `meta.code_map`)
— see rule_report_ai/catalogue.py's docstring for why that knowledge must
NOT live in the generic chat. Produces a document, never a RuleReportSpec —
nothing here touches the DSL engine or the chat's JSON output path.
"""
