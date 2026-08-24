from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


INK = colors.HexColor("#12201c")
MUTED = colors.HexColor("#5d706a")
GREEN = colors.HexColor("#78a900")
CYAN = colors.HexColor("#168f83")
PALE = colors.HexColor("#eef5f1")
LINE = colors.HexColor("#cddbd5")


def _safe(value, fallback="Nao informado"):
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", _safe(value, "microservico").lower()).strip("-")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=28,
                                leading=32, textColor=INK, alignment=TA_LEFT, spaceAfter=8),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontSize=12, leading=18,
                                   textColor=MUTED, spaceAfter=14),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18,
                             leading=22, textColor=INK, spaceBefore=6, spaceAfter=10),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13,
                             leading=16, textColor=CYAN, spaceBefore=8, spaceAfter=7),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontSize=9, leading=13, textColor=INK),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontSize=7.5, leading=10, textColor=MUTED),
        "metric": ParagraphStyle("Metric", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=17,
                                 leading=20, textColor=GREEN, alignment=TA_CENTER),
        "metric_label": ParagraphStyle("MetricLabel", parent=base["BodyText"], fontSize=7, leading=9,
                                       textColor=MUTED, alignment=TA_CENTER),
        "metric_box": ParagraphStyle("MetricBox", parent=base["BodyText"], fontSize=7, leading=18,
                                     textColor=MUTED, alignment=TA_CENTER),
        "cover_label": ParagraphStyle("CoverLabel", parent=base["BodyText"], fontName="Helvetica-Bold",
                                      fontSize=8, leading=10, textColor=CYAN, spaceAfter=4),
    }


def _p(value, style):
    text = _safe(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _table(rows, widths, header=True, font_size=8):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PALE]),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                     ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    table.setStyle(TableStyle(commands))
    return table


def _header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(CYAN)
    canvas.drawString(18 * mm, height - 11.5 * mm, "EXPERT CODE FLOW - RELATORIO DE MATURIDADE")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def _metrics(report, styles):
    confidence = {"HIGH": "Alta", "MEDIUM": "Media", "LOW": "Baixa",
                  "NOT_AVAILABLE": "Nao disponivel"}.get(report.get("confidence"), _safe(report.get("confidence")))
    values = [
        ("SCORE GERAL", "N/A" if report.get("score") is None else f'{report.get("score")}/100'),
        ("COBERTURA", f'{report.get("coverage_percent", "N/A")}%'),
        ("CONFIANCA", confidence),
        ("REGRAS AVALIADAS", f'{report.get("evaluated_criteria", 0)}/{report.get("applicable_criteria", 0)}'),
    ]
    row = [Paragraph(f'{label}<br/><font name="Helvetica-Bold" size="17" color="#78a900">{value}</font>',
                     styles["metric_box"]) for label, value in values]
    return _table([row], [42*mm] * 4, header=False)


def build_maturity_report(report: dict, xray: dict, output_dir: Path) -> Path:
    styles = _styles()
    context = report.get("context") or {}
    service = context.get("project_name") or xray.get("microservice") or "microservico"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"relatorio-maturidade-{_slug(service)}.pdf"
    doc = BaseDocTemplate(str(target), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                          topMargin=22*mm, bottomMargin=17*mm, title=f"Maturidade - {service}",
                          author="Expert Code Flow")
    doc.addPageTemplates(PageTemplate(id="report", frames=[Frame(doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="content")], onPage=_header_footer))
    story = []

    story += [Spacer(1, 18*mm), _p("RELATORIO TECNICO E EXECUTIVO", styles["cover_label"]),
              _p("Maturidade do Microservico", styles["title"]),
              _p(f"Diagnostico consolidado de arquitetura, inventario estrutural, endpoint e criterios objetivos para <b>{_safe(service)}</b>.", styles["subtitle"]),
              Spacer(1, 5*mm)]
    cover_rows = [
        [_p("Microservico", styles["small"]), _p(service, styles["body"])],
        [_p("Endpoint avaliado", styles["small"]), _p(context.get("endpoint"), styles["body"])],
        [_p("Arquitetura detectada", styles["small"]), _p(context.get("architecture"), styles["body"])],
        [_p("Projeto", styles["small"]), _p(context.get("project_path"), styles["body"])],
        [_p("Processado em", styles["small"]), _p(report.get("generated_at") or datetime.now().isoformat(), styles["body"])],
    ]
    story += [_table(cover_rows, [42*mm, 126*mm], header=False), Spacer(1, 8*mm), _metrics(report, styles),
              Spacer(1, 10*mm), _p("Leitura executiva", styles["h2"])]
    score = report.get("score")
    coverage = report.get("coverage_percent")
    story.append(_p(f"O servico obteve score <b>{score if score is not None else 'N/A'}/100</b>, com cobertura de <b>{coverage if coverage is not None else 'N/A'}%</b>. Regras nao aplicaveis foram excluidas do calculo; regras sem evidencia conclusiva permanecem identificadas como nao avaliadas.", styles["body"]))
    story += [PageBreak(), _p("1. Raio-X do microservico", styles["h1"])]

    code = xray.get("code") or {}
    architecture = xray.get("architecture") or {}
    integrations = xray.get("integrations") or {}
    story += [_p("Dimensao do codigo", styles["h2"]),
              _table([["Arquivos Java", "Classes", "Interfaces", "Metodos", "Linhas", "Dependencias"],
                      [code.get("java_files", 0), code.get("classes", 0), code.get("interfaces", 0),
                       code.get("methods", 0), code.get("lines_of_code", 0), code.get("dependencies", 0)]], [28*mm]*6),
              Spacer(1, 4*mm)]
    story += [_p("Estrutura Spring e arquitetural", styles["h2"]),
              _table([["Controllers", "Endpoints", "Services", "Ports IN", "Ports OUT", "Adapters OUT", "Repositories", "Entidades JPA"],
                      [architecture.get("rest_controllers",0), architecture.get("rest_endpoints",0),
                       architecture.get("services",0), architecture.get("ports_in",0), architecture.get("ports_out",0),
                       architecture.get("adapters_out",0), architecture.get("repositories",0), architecture.get("jpa_entities",0)]], [21*mm]*8, font_size=7),
              Spacer(1, 4*mm)]
    story += [_p("Integracoes", styles["h2"]),
              _table([["Chamadas externas", "Bancos", "Produtores de eventos", "Consumidores de eventos"],
                      [integrations.get("external_calls",0), integrations.get("databases",0),
                       integrations.get("event_producers",0), integrations.get("event_consumers",0)]], [42*mm]*4),
              Spacer(1, 4*mm)]
    versions = xray.get("versions") or {}
    if versions:
        story += [_p("Versoes identificadas", styles["h2"]),
                  _table([["Tecnologia", "Versao"]]+[[key, value] for key, value in versions.items()], [84*mm,84*mm])]
    dependencies = xray.get("dependencies") or []
    if dependencies:
        story += [Spacer(1, 4*mm), _p("Dependencias declaradas", styles["h2"]),
                  _table([["Dependencia","Grupo","Versao","Escopo"]]+[[_safe(d.get("name")),_safe(d.get("group"),"-"),
                          _safe(d.get("version"),"-"),_safe(d.get("scope"),"-")] for d in dependencies],
                         [51*mm,51*mm,33*mm,33*mm], font_size=7)]

    story += [PageBreak(), _p("2. Resultado de maturidade", styles["h1"]), _metrics(report, styles), Spacer(1, 5*mm)]
    dimensions = report.get("dimensions") or []
    dimension_rows = [["Dimensao", "Peso", "Score", "Cobertura", "Confianca", "Avaliadas / aplicaveis"]]
    for dimension in dimensions:
        dimension_rows.append([_safe(dimension.get("dimension")), f'{round((dimension.get("weight") or 0)*100)}%',
                               "N/A" if dimension.get("score") is None else dimension.get("score"),
                               "N/A" if dimension.get("coverage_percent") is None else f'{dimension.get("coverage_percent")}%',
                               _safe(dimension.get("confidence")),
                               f'{dimension.get("summary",{}).get("evaluated_applicable",0)} / {dimension.get("summary",{}).get("applicable",0)}'])
    story += [_table(dimension_rows, [45*mm,18*mm,20*mm,24*mm,27*mm,34*mm], font_size=7.5), Spacer(1, 6*mm)]

    all_criteria = [criterion for dimension in dimensions for criterion in dimension.get("criteria", [])]
    priorities = [c for c in all_criteria if c.get("result") == "NON_ADHERENT" or c.get("processing_status") == "NOT_EVALUATED"]
    story += [_p("Prioridades recomendadas", styles["h2"])]
    if priorities:
        priority_rows = [["Regra", "Criterio", "Situacao", "Motivo"]]
        for criterion in priorities[:12]:
            situation = "Nao avaliado" if criterion.get("processing_status") == "NOT_EVALUATED" else "Nao aderente"
            priority_rows.append([criterion.get("id"), _p(criterion.get("criterion"), styles["small"]), situation,
                                  _p(criterion.get("reason"), styles["small"])])
        story.append(_table(priority_rows, [28*mm,43*mm,28*mm,69*mm], font_size=7))
    else:
        story.append(_p("Nenhuma prioridade critica foi identificada no processamento atual.", styles["body"]))

    story += [PageBreak(), _p("3. Auditoria detalhada dos criterios", styles["h1"]),
              _p("O apendice preserva a rastreabilidade entre regra, resultado, justificativa e evidencia.", styles["subtitle"])]
    labels = {"ADHERENT":"Aderente", "PARTIALLY_ADHERENT":"Parcialmente aderente",
              "NON_ADHERENT":"Nao aderente", "NOT_APPLICABLE":"Nao aplicavel"}
    for dimension in dimensions:
        story += [_p(_safe(dimension.get("dimension")), styles["h2"])]
        rows = [["Regra", "Subdimensao / criterio", "Resultado", "Justificativa / evidencia"]]
        for criterion in dimension.get("criteria", []):
            result = labels.get(criterion.get("result"), "Nao avaliado")
            evidence = (criterion.get("evidence") or [{}])[0]
            finding = evidence.get("finding") or evidence.get("snippet") or criterion.get("reason")
            rows.append([criterion.get("id"),
                         _p(f"<b>{_safe(criterion.get('subdimension'))}</b><br/>{_safe(criterion.get('criterion'))}", styles["small"]),
                         result, _p(finding, styles["small"])])
        story += [_table(rows, [27*mm,51*mm,31*mm,59*mm], font_size=7), Spacer(1, 5*mm)]

    story += [PageBreak(), _p("4. Metodologia e interpretacao", styles["h1"]),
              _p("A avaliacao utiliza criterios objetivos versionados. Aderente vale 1, parcialmente aderente vale 0,5 e nao aderente vale 0. Criterios nao aplicaveis sao excluidos. Criterios nao avaliados valem zero e reduzem score, cobertura e confianca.", styles["body"]),
              Spacer(1, 4*mm),
              _p("Este relatorio e um diagnostico estatico do codigo e das configuracoes disponiveis no momento da analise. Ele apoia decisoes tecnicas, mas nao substitui testes de carga, verificacoes em runtime, revisao de seguranca ou validacao humana.", styles["body"])]
    doc.build(story)
    return target
