# Current GEstimator vs OpenAEC B2 — preview

Open `comparison.html` for the self-contained interactive comparison. It includes dark/light themes, Schedule/Analysis screenshots, a native-size screenshot viewer, and icon comparisons at 16 px, 24 px and 48 px (2× detail).

`comparison-dark.png` and `comparison-light.png` are shareable boards. The individual `schedule-*` and `analysis-*` PNGs show the full 1440×900 workbench.

Both alternatives use the same GEstimator project, layout, theme and colours. The proposed screenshots replace matching SVGs in the browser at capture time; production components were not changed. The browser harness uses the real Python service with the desktop transport shim. The gallery renders the actual upstream B2 geometry, choosing the 16 px master for 16 px output and the 24 px master for larger output.

`icon-data.json` records the current GEstimator drawings, explicit semantic mappings, and the selected upstream geometry. Unmapped actions retain their current artwork. In particular, Paste has no equivalent in the imported B2 selection. The B2 Resources example uses Planner's `resource.workspace` people symbol; a final migration should choose an appropriate material/equipment symbol for GEstimator where needed.

Source: https://github.com/OpenAEC-Foundation/open-planner-studio/blob/main/src/components/icons/b2/icons.generated.ts

Blueprint commit recorded by upstream: `ca4e60ac187b3c6401ef557bb11000255c1f4d6a`, B2 revision 107. See `NOTICE.txt` and the included LGPL/GPL texts for source and licence notices.
