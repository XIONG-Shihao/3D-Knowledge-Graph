# Proposal: 3D graph with screen-facing labels

Date: 2026-10-08. Status: **proposed; not implemented**.

Atlas currently ships a 2D Cytoscape graph. This proposal adds an optional 3D view with flat, upright labels that face the user. It changes how existing knowledge is displayed, not how relationships are extracted or verified. See [PRODUCT.md](PRODUCT.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [the README](../README.md) for the current MVP.

## 1. Design decision

**Place nodes and connections in 3D; keep labels flat to the screen.** Keep the existing 2D view as the default and offer a `2D / 3D` switch after the prototype passes validation.

Imagine `张伟` as a sphere floating in space, with a small name card beside it. Rotating the graph moves the sphere and card across the screen, but the characters stay upright. Selecting its `负责` connection opens the same evidence for `知识图谱项目` that is available in 2D.

This addresses text orientation. It does not automatically solve overlap: nodes at different depths can project onto the same screen position. Label visibility must therefore be managed separately from the 3D layout.

## 2. User experience

| Element | Proposed behavior |
|---|---|
| Nodes | 3D spheres; retain type colors and selected/neighbor emphasis |
| Connections | 3D lines with direction arrows; selected edges are emphasized |
| Node labels | Flat, horizontal text anchored near the projected node; readable CSS font size independent of camera distance |
| Relationship labels | Show for hovered/selected edges and relevant focused connections; avoid labeling every edge in a crowded view |
| Camera | Orbit, pan, zoom, fit visible graph and reset; no automatic spinning |
| Focus | Selecting a node highlights its neighbors; a separate focus action moves the camera to that region |
| Source inspector | Reuse document/chunk links, origin labels and unresolved-reference behavior |
| View switch | Preserve knowledge base, filters and selected node/edge ID; keep separate camera/layout state for each view |
| Fallback | If WebGL or the 3D module fails, keep 2D usable and show a concise explanation |

The graph's existing topic/node list remains a keyboard-accessible route to selection. Camera movement is supplemental; users should not have to navigate 3D space to inspect a source. Provide visible controls with Chinese and English interface labels. Respect reduced-motion preferences for camera transitions.

## 3. Label rendering

Two approaches can keep labels facing the user:

| Approach | Advantages | Constraints |
|---|---|---|
| WebGL text sprites / billboards | Labels remain part of the 3D scene and face the camera | Text resolution, apparent size and overlap need explicit control; fonts must be ready before generating text textures |
| HTML labels projected onto a 2D overlay | Browser renders Chinese text crisply; CSS controls size, wrapping, contrast and interactions | Requires explicit positioning, collision handling and a limit on visible DOM labels |

Three.js [sprites face the camera](https://threejs.org/docs/pages/Sprite.html). Its [CSS2DRenderer supports HTML labels combined with 3D objects](https://threejs.org/docs/pages/CSS2DRenderer.html), but documents a browser/display zoom restriction of 100%.

**Recommended first prototype: an HTML overlay with explicitly projected node positions.** Use the camera to map each 3D anchor into the graph container's screen coordinates and position a label there without rotation or perspective scaling. This gives direct control over fixed text size, collisions and browser zoom behavior. CSS2DRenderer and sprites remain alternatives to benchmark; their behavior should not be assumed to meet the acceptance criteria automatically.

Proposed text rules:

- Start at 16 CSS pixels for ordinary labels; selected labels may be larger. This is a design target, not a measured implementation.
- Use available Chinese-capable system fonts with a sans-serif fallback. Validate both Mac and Linux client rendering; server OS does not determine browser fonts.
- Give labels a contrasting background and spacing so connections remain visible behind them.
- Wrap or shorten long labels by available screen width. Show the full original label in the inspector; never alter the stored label.
- Insert label content as text, not untrusted HTML.
- When labels are moved away from an anchor to avoid overlap, use a short leader line so the associated node remains clear.

## 4. Overlap and visibility rules

Use screen-space label rectangles, not just distances between nodes in the 3D layout.

1. Exclude nodes behind the camera, outside the viewport or hidden by filters.
2. Prioritize the selected node/edge, then hovered objects, focused neighbors, search matches and other visible nodes.
3. Reserve space for the selected label. Try a few nearby offsets for the next labels, hiding lower-priority labels when they still collide.
4. Keep labels within the graph container and away from controls and the source panel.
5. Apply a configurable visible-label budget. The first prototype should start with 40 ordinary labels, then adjust based on readability and performance measurements.
6. Stabilize visibility during camera movement so labels do not flicker between nearly equal priorities. Recalculate after camera/layout changes and container resize.

Label hiding must not hide the node itself or make it unselectable. Hovering a node reveals its full label where space allows; selecting it exposes the full name in the inspector even when the projected anchor is offscreen.

An HTML overlay does not automatically obey 3D depth occlusion. Start with hidden labels for offscreen/behind-camera anchors and priority-based overlap handling. Evaluate node occlusion on real graphs before adding expensive per-label visibility checks. Selected labels should remain identifiable rather than mysteriously disappearing behind other nodes.

## 5. Frontend integration

Use [3d-force-graph](https://github.com/vasturiano/3d-force-graph) as the candidate 3D graph renderer; it is built on Three.js/WebGL. Exact package versions will be selected and locked when implementation starts. No new dependencies are installed by this documentation change.

Proposed components:

| Component | Responsibility |
|---|---|
| Shared graph view state | Knowledge-base ID, normalized graph, filters, selected object ID and source-inspector state |
| 2D renderer adapter | Existing Cytoscape behavior behind the shared selection/filter interface |
| 3D renderer adapter | Graph copies, 3D layout, camera, picking, highlights and lifecycle cleanup |
| Label overlay | Screen projection, font styling, collision priority, label budget and safe text rendering |

Keep the API's normalized `nodes` and `edges` as the source of truth. Copy nodes and edges before handing them to the simulation; adapt `edges` to the renderer's `links`. The renderer may mutate coordinates and replace endpoint IDs with node objects, so callbacks must resolve the stable original IDs before selecting an edge or opening evidence.

`x/y/z`, camera position and label offsets are view state. Do not write them into imported knowledge JSON or treat spatial proximity as a semantic relationship. Basic 3D requires no graph database change, new RAGFlow endpoint or model configuration. Local, imported and remote graphs use the same path.

Load the 3D module only when requested to avoid adding its initial download and GPU work to ordinary 2D use. Dispose of animation loops, observers, event handlers, overlay elements and GPU resources when changing knowledge bases or destroying the view. Retain a paused or saved camera state when appropriate rather than resetting on every selection.

Keep browser dependencies bundled in the release, without runtime CDN imports. The native Linux installation and no-Docker deployment remain the same; 3D runs in the user's browser. Linux release packaging must include the updated compiled frontend after implementation.

## 6. Scope

The first implementation should include an optional 3D view, flat labels, overlap priorities, camera controls, filters, selection, source inspection and 2D fallback.

Defer VR/headset navigation, stereoscopic rendering, editable coordinates, persisted layouts, new entity extraction, new RAGFlow artifact automation and promises about rendering the maximum import size smoothly. These would be separate changes with separate validation.

## 7. Implementation sequence

1. Extract shared selection/filter behavior from the existing graph view; confirm 2D source inspection still works.
2. Add a lazy-loaded 3D renderer for the same normalized data and stable IDs. Add camera controls and lifecycle cleanup.
3. Add projected HTML labels, Chinese fonts, collision rules and focus behavior.
4. Connect node/edge selection to the existing inspector; preserve filters and selection across view switches.
5. Verify accessibility, browser zoom, fallback and performance, then package and document the implemented status.

Do not mark 3D as shipped in the README until the functional acceptance checks pass. No implementation schedule or performance result is established by this proposal.

## 8. Acceptance criteria

| Check | Required outcome |
|---|---|
| Rotate the Chinese example | `张伟` and `知识图谱项目` stay flat, upright and readable throughout the orbit |
| Zoom the camera | Label text stays at the configured screen size; distant nodes can have labels hidden by priority |
| Zoom the browser to 125% and 150% | Labels stay aligned with nodes and controls remain usable; also validate display scaling |
| Dense overlapping nodes | Prioritized labels avoid collisions; selected names remain available; hidden labels do not prevent node selection |
| Select the `负责` edge | The correct edge ID reaches the inspector and its existing document/chunk evidence remains available |
| Imported unknown source reference | It remains unresolved in both 2D and 3D; no fabricated citation appears |
| Switch views and filters | Knowledge base, filters and selection are preserved; hidden objects do not remain accidentally interactive |
| Keyboard and reduced motion | Node-list selection and source inspection work without camera gestures; optional transitions respect reduced motion |
| Missing WebGL or module failure | The 2D graph and source inspector remain usable |
| Repeated view/workspace changes | No accumulated canvas/overlay elements, animation loops or event listeners |

For initial performance evaluation, use small Chinese fixtures and a representative graph of 200 nodes / 400 edges. Target at least 30 frames per second during a short camera orbit with the proposed label budget on recorded reference hardware. This is a prototype target, not a guarantee. Record browser, device/GPU, visible labels and frame timings; test larger graphs separately and reduce visible labels or offer 2D when the interaction becomes slow.

Acceptance should compare real tasks in both views: find a person, identify a relationship and open its source. A visually attractive 3D scene is insufficient if these tasks become harder.
