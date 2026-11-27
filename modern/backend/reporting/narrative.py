"""Bounded Jinja field/conditional templates, rendered once to escaped plain text."""

from dataclasses import dataclass

from jinja2 import StrictUndefined, TemplateError, nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment

ALLOWED = (
    nodes.Template,
    nodes.Output,
    nodes.TemplateData,
    nodes.Name,
    nodes.Const,
    nodes.Filter,
    nodes.If,
    nodes.Compare,
    nodes.Operand,
    nodes.Not,
    nodes.And,
    nodes.Or,
    nodes.CondExpr,
)
FIELDS = (
    "project_name",
    "name_of_work",
    "title",
    "organization",
    "office",
    "reference",
    "issue_date",
    "estimate_total",
    "item_count",
    "category_count",
)


@dataclass(frozen=True)
class Narrative:
    """Rendered pages detached from request values and project models."""

    id: str
    pages: tuple[str, ...]


def render(source, context):
    """Allow substitution, conditionals and small text filters; reject calls/loops/imports.

    Parsing the allowlisted AST before compilation prevents repeated expansion or
    arbitrary computation. Only primitive estimate strings enter the environment.
    """
    environment = ImmutableSandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
    environment.globals.clear()
    environment.filters = {key: environment.filters[key] for key in ("upper", "lower", "title", "trim", "default")}
    try:
        tree = environment.parse(source)
        children = list(tree.find_all(nodes.Node))
        if len(children) > 2000 or any(not isinstance(node, ALLOWED) for node in children):
            raise ValueError(
                "Notes support estimate fields, if conditions and text filters; calls, loops and imports are unavailable"
            )
        if any(isinstance(node, nodes.Name) and node.name not in FIELDS for node in children):
            raise ValueError("Unknown estimate field in notes")
        result, size = [], 0
        for chunk in environment.from_string(tree).generate(context):
            size += len(chunk)
            if size > 100000:
                raise ValueError("Rendered notes exceed 100000 characters")
            result.append(chunk)
        return "".join(result)
    except (TemplateError, RecursionError) as error:
        raise ValueError(f"Invalid notes template: {error}") from error


def build_narratives(document):
    """Resolve every enabled notes instance against the captured estimate, not live data."""
    spec = document.specification
    context = dict(
        project_name=document.project,
        name_of_work=document.project,
        title=spec.title,
        organization=spec.organization,
        office=spec.office,
        reference=spec.reference,
        issue_date=spec.issue_date,
        estimate_total=document.total,
        item_count=str(sum(bool(row.unit) for row in document.schedule)),
        category_count=str(len(document.abstract)),
    )
    return tuple(
        Narrative(section.id, tuple(render(page, context) for page in section.body.split("\f")))
        if section.kind == "narrative"
        else Narrative(section.id, (render(section.signoff_intro, context),))
        for section in spec.sections
        if section.enabled and (section.kind == "narrative" or section.kind == "signoff" and section.signoff_intro)
    )
