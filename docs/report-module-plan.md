# Report module proposal and rendering experiment

Status: core Reports workspace and exports implemented, 2026-11-26.
This is a proposal; the implemented subset has a separate
[report document contract](features/report-documents.md). Navigation: [index](README.md) · [roadmap](roadmap.md).

## Goal and scope

Add a Report workspace for composing estimate documents and exporting Excel,
PDF and standalone HTML. Keep the existing workbook export available. Users
select, reorder and configure sections: facing page, contents, abstract of
estimate, schedule, analyses, resources, resource usage, measurements, narrative
and signoff. An abstract summarizes category amounts and the overall estimate;
it does not introduce taxes or other estimating calculations.

The prototype in [tools/report_prototype](../tools/report_prototype/render.py)
tests Jinja2 plus WeasyPrint, following the rendering approach used in
[GElectrical](https://github.com/manuvarkey/GElectrical/blob/master/gelectrical/model/project.py).
It supports deterministic demonstration rows or accepted real-project snapshots
through `--project`. The application now has a Reports workspace for the initial
abstract/schedule/analysis/resource/usage/signoff sections, fixed-layout preview and HTML/Excel exports,
plus PDF through an installed WeasyPrint 70+ CLI. Report definitions can be applied to the working project and persisted through
normal project Save. There is no new application runtime Python dependency. The fixed
application renderer is independent of the trusted custom-template experiment.

## Try the prototype

From the repository root:

```sh
.venv/bin/pip install -r tools/report_prototype/requirements.txt
.venv/bin/python -m tools.report_prototype.render /tmp/estimate-demo --logo /path/to/logo.png
.venv/bin/python -m unittest tools.report_prototype.test_render
```

To render a real project without modifying its source file:

```sh
.venv/bin/python -m tools.report_prototype.render /tmp/project-report --project /path/to/project.eproj --organization "Office name"
```

This uses the shared snapshot amounts without recalculating analyses. Dirty
live-session drafts are protected by the backend API; this file-based experiment
reads the selected saved file in a separate isolated session.

To exercise the executable route on Linux, use the installed CLI:

```sh
.venv/bin/python -m tools.report_prototype.render /tmp/estimate-cli --executable .venv/bin/weasyprint --timeout 60
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m unittest tools.report_prototype.test_render tools.report_prototype.test_executable
```

On Windows, extract the official onedir ZIP intact and use its executable:

```powershell
.venv\Scripts\python.exe -m tools.report_prototype.render estimate-cli --executable C:\Tools\WeasyPrint\onedir\weasyprint\weasyprint.exe --timeout 60
```

The CLI route imports Jinja2 and the shared calculation engine, but does not
import the optional WeasyPrint Python library/native text libraries. The current
prototype requirements install both renderers for comparison; a production
Windows backend can omit the WeasyPrint Python package when shipping the CLI.
The managed process receives UTF-8 HTML on stdin and writes into a fresh scratch
directory. It allows only `data:` resources, disables redirects, fails on asset
errors, hides its console on Windows and is killed/reaped on timeout. Diagnostics
are returned with successful output or included in failure errors. HTML/PDF are
published to a fresh output directory only after rendering succeeds. Existing
report files are never replaced by this experiment. Output directories can still
be incomplete on a later filesystem write failure; production must use the
existing safe publication boundary.

The prototype bounds HTML to 10 MB, checks the completed PDF against 50 MB and
returns at most 16 KB of diagnostics. These are experiment limits, not production
contracts or live memory/disk quotas. Cancellation during a running desktop job
and whole-process-tree termination remain future integration work. `onedir`
avoids the additional launcher/extraction behavior of `onefile`.

The output directory must not already exist. HTML contains inline CSS and an
embedded optional PNG/JPEG logo; PDF is rendered from the same HTML. The sample
has a facing page, linked contents with PDF page references, category abstract,
long schedule descriptions, repeated table headings, page counts and signoff.
Sections can be reordered/omitted with `--sections abstract schedule signoff`.
Use a portable fresh output directory on Windows instead of `/tmp/...`.

Copy any templates from [the default template directory](../tools/report_prototype/templates/report.html)
to a local directory, edit them, and pass `--templates /path/to/templates`.
Missing templates fall back to bundled defaults. In particular, override
`facing.html` and `abstract.html` independently. Context fields are defined in
the prototype's `context` function; monetary values are decimal strings. The
organization logo is the optional `logo` data URI. Custom templates may change
the layout and CSS freely, and must be intentionally authored/trusted. Autoescape,
strict missing-variable errors and the Jinja sandbox remain enabled. Project
descriptions are never compiled as templates. PDF resource fetching rejects
network/filesystem URLs; HTML has a restrictive content security policy.
This is an authoring experiment, not a security boundary for hostile templates;
production needs size/time limits and validated template import.

## Proposed production contracts

- A schema-versioned report specification contains ordered section instances,
  stable section IDs, titles, enabled state, item/category filters, columns,
  grouping and per-section layout settings.
- Document settings contain paper/margins, typography, headers/footers,
  numbering and signoff fields. Facing-page fields include organization name,
  logo, project/client, report title, reference, revision and issue date.
- Python builds an immutable report document from one project revision. It
  uses engine calculations and payable schedule selection; headings and
  dependency-only subanalyses must not enter abstract totals. No recalculation
  or draft acceptance occurs as a side effect of export.
- Vue edits specifications and renders previews. Service/editor boundaries
  retain revision checks and draft guards. Rust handles native destinations.
- HTML and PDF share section templates. Excel uses the same report document
  through a separate renderer, reusing workbook helpers where compatible.
  Excel contents link to sheets; final PDF contents reference actual pages.
- Production exports use the existing safe publication/portal boundary;
  cancellation and rendering failures must leave existing destinations intact.

Implemented persistence: a versioned optional JSON project setting for the
report definition, after archived-engine save/reopen preservation was proved.
Read failures preserve opaque data; explicit Apply and normal Save publish valid
definitions. Persisted row filters remain excluded until deletion/key reuse is
covered. Reusable office template bundles remain future work. Keep logos embedded and bounded; a saved
project must not depend on the author's external logo path. Do not store arbitrary
HTML in ordinary project text fields. Template bundles need validated paths,
asset types, schema upgrades and clear project-versus-office override behavior.

The supplied GElectrical `gelectrical/templates/report.html` and `report.css`
were reviewed on 2026-11-26 as layout references. GEstimator uses its own fixed,
escaped renderer with comparable nested contents, running section headings,
caption break controls and named landscape pages for wide resource tables.
No external template or stylesheet is loaded at runtime.

## Delivery sequence and gates

1. **Rendering experiment (this change):** default/custom facing and abstract,
   logo, page references, long tables, signoff, offline HTML/PDF. Record measured
   behavior and limits in the validation log.
2. **Foundation (initial subset implemented):** validated specification and
   immutable project adapter for schedule/abstract/signoff, real-project amount
   parity and read-only snapshot/revision/draft tests. Safe export publication is
   now shared with existing exports. The core analysis/resource/usage adapters
   are implemented; measurement/narrative datasets are also implemented.
3. **Complete workspace (core workflow implemented):** section editor, preview, Excel/HTML/PDF chooser,
   initial cover/contents/abstract/schedule/analysis/resource/usage/signoff
   sections, browser coverage, synchronized manual and architecture contracts.
   All listed core sections are available. Analysis results are evaluated only
   on detached models; catalog/usage reuse accepted engine data and rules.
4. **Customization (measurement/narrative subset implemented):** accepted measurement
   records, constants, separately labelled linked outputs and per-section plain-text
   notes are available in all formats. Fixed-table columns and per-section
   portrait/landscape settings and persisted project definitions are also implemented.
   Numbered collapsible settings, system-font selection/scaling, 20 mm margins,
   running headers/footers and proportional table widths are implemented.
   Bundled Iosevka, project/program estimate defaults, editable repeated signoffs,
   category/item contents, per-item pages and bounded Jinja notes are implemented.
   Remaining work: persisted row-selection lifecycle, office templates and template
   editor/import/export. Preserve existing project compatibility.
5. **Release hardening:** isolated render worker with cancellation/limits,
   large-project profiling, accessibility, font coverage, frozen sidecar and
   installed Windows/Linux package and Flatpak portal verification.

WeasyPrint 70 requires native text libraries including Pango. See its
[installation guide](https://doc.courtbouillon.org/weasyprint/v70.0/first_steps.html).
For Windows, prefer evaluating the official standalone executable before
building another frozen renderer. The [v70.0 release](https://github.com/Kozea/WeasyPrint/releases/tag/v70.0)
provides `weasyprint-windows-onedir.zip` (32,271,073 bytes) and
`weasyprint-windows-onefile.zip` (31,510,667 bytes). These asset names and sizes
were checked against the GitHub release API on 2026-11-24. The installation
guide explicitly recommends the executable for Windows; using the Python
library has separate native-library setup requirements.

Proposed Windows route: bundle the pinned `onedir` distribution intact and run
its executable in a managed child process against generated HTML. Keep Jinja2
and authoritative data preparation in Python. Verify the release checksum,
include applicable dependency notices, and test on a clean Windows machine.
The downloaded archive's SHA-256 was verified as
`ab1151f210b4e6bb7aa7a79e91a67e8ddb760094c107bfda55241b6aaefe7d53`.
Archive inspection confirmed `onedir/weasyprint/weasyprint.exe` plus Pango,
HarfBuzz and Fontconfig DLLs under `_internal`. Keep that directory layout intact.
The executable path is now implemented in the experiment and exercised with the
Linux CLI. It uses WeasyPrint 70's `--allowed-protocols data` option; unlike the
library fetcher, it permits all data URI asset types, not only raster images.
Custom templates remain trusted. Before production, validate imported assets,
add desktop cancellation and resource quotas. The application fixed-layout
workflow now uses safe export publication; the custom-template experiment keeps
its fresh-directory publication policy.
No Windows executable was run here; clean-machine installation, font discovery,
redistribution notices and antivirus behavior remain Windows verification gates.

Packaging libraries and fonts remains a release gate for each target;
a successful local PDF is not proof of distributable packages. Font
fallback, non-Latin scripts, very tall rows, mixed orientations, long contents,
and signature placement near page boundaries need separate fixtures. The
prototype checks Latin accented text and m² only. It does not establish CJK or
Indic font support. Visible page numbers include the unnumbered facing page in
the document count. Continuous HTML has navigation links rather than fixed page
numbers; PDF is the authoritative paginated output.
