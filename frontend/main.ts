import { highlight } from './highlight';
import { t, ui, getLanguage, setLanguage } from './i18n';
import cytoscape, { Core, ElementDefinition } from 'cytoscape';
import {
  createIcons, Waypoints, Layers2, Plus, FolderOpen, LockKeyhole, Settings2,
  ChevronRight, Plug, HardDrive, Files, Boxes, Network, ShieldCheck, Search,
  RefreshCw, Orbit, Upload, Hash, UserRound, Building2, Box, Cpu, Circle,
  FileText, Minus, Scan, Shuffle, Download, Sparkles, X, GitBranch, ArrowRight,
  ArrowUpRight, Info, FileJson, WandSparkles, CloudUpload, ListTree, RotateCw, Trash2,
} from 'lucide';
const icons = {
  Waypoints, Layers2, Plus, FolderOpen, LockKeyhole, Settings2,
  ChevronRight, Plug, HardDrive, Files, Boxes, Network, ShieldCheck, Search,
  RefreshCw, Orbit, Upload, Hash, UserRound, Building2, Box, Cpu, Circle,
  FileText, Minus, Scan, Shuffle, Download, Sparkles, X, GitBranch, ArrowRight,
  ArrowUpRight, Info, FileJson, WandSparkles, CloudUpload, ListTree, RotateCw, Trash2,
};
import './style.css';

type KB = { id: string; name: string; description: string; backend: string; document_count: number; chunk_count: number; dataset_id?: string; graph_status?: string };
type Doc = { id: string; name: string; status: string; size: number; progress: number; error: string; chunk_count: number; topics: string[]; remote_id?: string; chunks?: Chunk[] };
type Chunk = { id: string; doc_id: string | null; document_name: string; ordinal?: number; content: string; score?: number; page?: number };
type Node = { id: string; label: string; type: string; description: string; source_documents: string[]; source_refs?: string[]; origin: string };
type Edge = { id: string; source: string; target: string; relation: string; description: string; source_documents: string[]; source_chunks?: string[]; source_refs?: string[]; origin: string };
type Graph = { nodes: Node[]; edges: Edge[]; origin: string; status?: string; error?: string };
type Topic = { label: string; documents: { id: string; name: string }[] };
type Config = { ragflow_configured: boolean; legacy_graph_api: boolean; max_upload_mb: number };
type View = 'graph' | 'documents' | 'search';
const app = document.querySelector<HTMLDivElement>('#app')!;
let bases: KB[] = [], docs: Doc[] = [], topics: Topic[] = [];
let graph: Graph = { nodes: [], edges: [], origin: 'local' };
let config: Config = { ragflow_configured: false, legacy_graph_api: false, max_upload_mb: 20 };
let current = '', view: View = 'graph', cy: Core | undefined, selected: Node | Edge | undefined;
let query = '', graphFilter = '', results: Chunk[] = [], searchMode = 'keyword';
let lastSearch = '', searchBusy = false, syncBusy = false, loadVersion = 0, searchVersion = 0;
let typeFilters = new Set<string>();
const palette: Record<string, { color: string; border: string; icon: string }> = {
  document: { color: '#dfeae6', border: '#83a798', icon: 'file-text' },
  topic: { color: '#e4dff5', border: '#a097ca', icon: 'hash' },
  person: { color: '#f5e7ca', border: '#c9aa69', icon: 'user-round' },
  organization: { color: '#d1e7ed', border: '#78adb9', icon: 'building-2' },
  project: { color: '#d9e4fa', border: '#829cc5', icon: 'box' },
  technology: { color: '#dce9d0', border: '#93ac79', icon: 'cpu' },
  concept: { color: '#e4dff5', border: '#a097ca', icon: 'circle' },
};
const esc = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
const icon = (name: string, cls = '') => ui`<i data-lucide="${name}" class="${cls}"></i>`;
const pretty = (text: string) => t(text.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()));
const kb = () => bases.find(b => b.id === current);
const baseURL = () => `/api/knowledge-bases/${encodeURIComponent(current)}`;
const edgeLabel = (edge: Edge) => edge.origin === 'local' ? t('Covers') : edge.relation;
const formatSize = (bytes: number) => bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }));
    throw new Error(typeof body.detail === 'string' ? body.detail : t('Check the fields and try again.'));
  }
  return response.status === 204 ? undefined as T : response.json();
}
const post = <T>(path: string, body?: unknown) => api<T>(path, { method: 'POST', ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
function drawIcons() { createIcons({ icons, attrs: { 'stroke-width': 1.7 } }); }
function toast(message: string, error = false) {
  message = t(message);
  const el = document.createElement('div');
  el.className = `toast ${error ? 'error' : ''}`;
  el.setAttribute('role', error ? 'alert' : 'status');
  el.textContent = message;
  document.body.appendChild(el);
  window.setTimeout(() => el.remove(), error ? 8000 : 4000);
}
function on(selector: string, event: string, handler: (event: Event) => void) {
  app.querySelector(selector)?.addEventListener(event, handler);
}
function withError(action: () => Promise<void>) { action().catch(e => toast(e.message, true)); }

async function refresh() {
  const version = ++loadVersion, id = current;
  bases = await api<KB[]>('/api/knowledge-bases');
  if (!id) current = bases[0]?.id || '';
  if (!current) { render(); return; }
  const target = current;
  const loaded = await Promise.all([
    api<Doc[]>(`${baseURL()}/documents`), api<Graph>(`${baseURL()}/graph`), api<Topic[]>(`${baseURL()}/topics`),
  ]);
  if (version !== loadVersion || target !== current) return;
  [docs, graph, topics] = loaded;
  if (selected) selected = graph.nodes.find(n => n.id === selected?.id) || graph.edges.find(e => e.id === selected?.id);
  render();
}

function render() {
  cy?.destroy(); cy = undefined;
  const base = kb(), ready = docs.filter(d => d.status === 'ready').length;
  app.innerHTML = ui`
  <aside class="sidebar">
    <a href="/" class="brand" aria-label="Atlas home"><span class="brand-mark">${icon('waypoints')}</span>atlas<span class="brand-dot">.</span></a>
    <div class="sidebar-label">YOUR WORKSPACE</div>
    <button class="workspace-item active" id="home-workspace">${icon('layers-2')}<span>Knowledge library</span></button>
    <div class="sidebar-label bases-heading">KNOWLEDGE BASES <button id="add-base" class="icon-button" aria-label="Create knowledge base">${icon('plus')}</button></div>
    <div class="base-list">${bases.map(b => ui`<button class="base-item ${b.id === current ? 'selected' : ''}" data-base="${esc(b.id)}">${icon('folder-open')}<span>${esc(b.name)}</span><small>${b.document_count}</small></button>`).join('')}</div>
    <div class="sidebar-bottom">
      <div class="local-note"><span class="status-dot"></span><div>Local workspace<small>Stored on this computer</small></div>${icon('lock-keyhole')}</div>
      <button id="settings" class="workspace-item">${icon('settings-2')}<span>Connections & help</span></button>
      <div class="profile"><span class="avatar">A</span><div>Personal workspace<small>Single-user MVP</small></div><span class="version">v0.1</span></div>
    </div>
  </aside>
  <main class="main">
    <header class="topbar"><div class="breadcrumb">Library ${icon('chevron-right')} <strong>${esc(base?.name || t('Welcome'))}</strong></div><div class="topbar-actions"><button id="language-toggle" class="language-toggle" aria-label="${getLanguage() === 'zh-CN' ? 'Switch to English' : '切换为中文'}">${getLanguage() === 'zh-CN' ? 'English' : '中文'}</button><button class="mode-badge" id="connection-badge" aria-label="Connections and help">${icon(base?.backend === 'ragflow' ? 'plug' : 'hard-drive')} ${base?.backend === 'ragflow' ? t('RAGFlow configured') : t('Local mode')}</button></div></header>
    <section class="page-heading"><div><div class="eyebrow">KNOWLEDGE, CONNECTED</div><h1>${esc(base?.name || t('Your knowledge starts here'))}</h1><p>${esc(base?.description || t('Add documents. Find ideas. Explore how they connect.'))}</p></div><button class="button primary" id="upload-button" ${!current ? 'disabled' : ''}>${icon('plus')} Add documents</button></section>
    ${base ? ui`<div class="stats"><span>${icon('files')}<strong>${ready}</strong> ready documents</span><span>${icon('boxes')}<strong>${base.chunk_count}</strong> knowledge chunks</span><span>${icon('network')}<strong>${graph.nodes.length}</strong> graph nodes</span><span class="stats-last">${icon('shield-check')} Traceable to sources</span></div>` : ''}
    <nav class="view-tabs" aria-label="Workspace views"><div>${(['graph', 'documents', 'search'] as View[]).map(v => ui`<button class="tab ${view === v ? 'active' : ''}" data-view="${v}">${icon(v === 'graph' ? 'network' : v === 'documents' ? 'files' : 'search')}${v === 'graph' ? t('Graph explorer') : pretty(v)}${v === 'documents' ? ui`<span class="count">${docs.length}</span>` : ''}</button>`).join('')}</div><button class="text-button" id="sync" ${syncBusy || !current ? 'disabled' : ''}>${icon('refresh-cw', syncBusy ? 'spin' : '')}${syncBusy ? t('Refreshing…') : t('Refresh')}</button></nav>
    <section id="view" class="view">${!base ? empty('layers-2', t('Make room for your ideas'), t('Create a knowledge base to start organizing documents.'), ui`<button class="button primary" id="empty-create">Create knowledge base</button>`) : view === 'graph' ? graphView() : view === 'documents' ? documentsView() : searchView()}</section>
  </main><input type="file" id="upload-input" multiple accept=".md,.txt,.pdf,.docx" hidden><input type="file" id="graph-input" accept=".json,application/json" hidden>`;
  bind(); drawIcons();
  if (view === 'graph' && base) drawGraph();
}

function empty(name: string, title: string, description: string, extra = '') {
  return ui`<div class="empty-state"><span class="empty-icon">${icon(name)}</span><h2>${esc(title)}</h2><p>${esc(description)}</p>${extra}</div>`;
}

function graphView() {
  const types = [...new Set(graph.nodes.map(n => n.type))];
  return ui`<div class="graph-layout"><section class="graph-card">
    <div class="graph-toolbar"><div class="graph-title">${icon('orbit')}<strong>Knowledge map</strong><span class="small-badge">${graph.origin === 'local' ? t('Document & topic map') : graph.origin === 'ragflow' ? t('RAGFlow extraction') : t('Imported graph')}</span></div><button class="text-button" id="import-graph">${icon('upload')} Import graph</button></div>
    <div class="graph-filter"><label class="filter-input">${icon('search')}<input id="graph-filter" placeholder="Find a node…" value="${esc(graphFilter)}" aria-label="Find a graph node"></label><div class="type-filters">${types.map(type => ui`<button class="type-chip ${typeFilters.has(type) ? 'off' : ''}" data-type="${esc(type)}"><span style="background:${palette[type]?.border || palette.concept.border}"></span>${esc(pretty(type))}</button>`).join('')}</div></div>
    <div class="node-search-results" id="node-results" hidden></div><div class="graph-stage"><div id="graph-canvas" role="img" aria-label="Interactive knowledge graph. Pan, zoom, or select a node to inspect its source documents."></div>
      ${!graph.nodes.length ? empty('network', t('Your connections will appear here'), t('Upload documents to organize topics, or import an extracted knowledge graph.')) : ''}
      <div class="canvas-caption"><span class="status-dot"></span>${graph.origin === 'local' ? t('Headings, keywords & author annotations') : graph.origin === 'ragflow' ? t('Machine-extracted relationships · review source evidence') : t('Imported relationships · verify source evidence')}</div>
      <div class="graph-controls"><button class="icon-button" id="zoom-in" aria-label="Zoom in">${icon('plus')}</button><button class="icon-button" id="zoom-out" aria-label="Zoom out">${icon('minus')}</button><span></span><button class="icon-button" id="fit" aria-label="Fit graph">${icon('scan')}</button><button class="icon-button" id="layout" aria-label="Rearrange graph">${icon('shuffle')}</button></div>
    </div>
    <div class="graph-footer"><span id="graph-count">${graph.nodes.length} nodes · ${graph.edges.length} connections</span><span>Drag to explore · Scroll to zoom</span><button class="text-button" id="export-graph">${icon('download')} Export</button></div>
  </section><aside class="inspector" id="inspector">${inspector()}</aside></div>`;
}

function inspector() {
  if (!selected) return ui`<div class="inspector-head"><span class="eyebrow">EXPLORER GUIDE</span>${icon('sparkles')}</div><div class="inspector-art"><div class="art-node center">${icon('network')}</div><div class="art-node n1">${icon('file-text')}</div><div class="art-node n2">${icon('hash')}</div><div class="art-node n3">${icon('file-text')}</div></div><h2>See the bigger picture.</h2><p class="muted">Your documents hold more than information. Explore the ideas and connections between them.</p><div class="guide-step"><span>01</span><div><strong>Follow a connection</strong><p>Select a node or a relationship to see what it means.</p></div></div><div class="guide-step"><span>02</span><div><strong>Go back to the source</strong><p>Open the supporting documents and inspect their text.</p></div></div><div class="inspector-section"><div class="section-label">TOP TOPICS</div>${topics.slice(0, 4).map(t => ui`<button class="topic-row" data-topic="${esc(t.label)}">${icon('hash')}<span>${esc(t.label)}</span><small>${t.documents.length}</small></button>`).join('') || ui`<p class="muted small">Topics appear after documents are processed.</p>`}</div>${graphActions()}`;
  const item = selected;
  const edge = 'relation' in item ? item : null;
  const node = 'label' in item ? item : null;
  const isEdge = Boolean(edge);
  const label = edge ? edgeLabel(edge) : node!.label;
  const sourceLabel = edge ? graph.nodes.find(n => n.id === edge.source)?.label : '';
  const targetLabel = edge ? graph.nodes.find(n => n.id === edge.target)?.label : '';
  const linked = isEdge ? [] : graph.edges.filter(e => e.source === selected!.id || e.target === selected!.id);
  return ui`<div class="inspector-head"><span class="eyebrow">${isEdge ? t('RELATIONSHIP') : t('NODE DETAILS')}</span><button class="icon-button" id="clear-selection" aria-label="Clear selection">${icon('x')}</button></div><span class="detail-symbol" style="background:${isEdge ? '#e8ede8' : palette[node?.type || 'concept']?.color || palette.concept.color}">${icon(isEdge ? 'git-branch' : palette[node?.type || 'concept']?.icon || 'circle')}</span><h2>${esc(label)}</h2>${isEdge ? ui`<div class="relation-label">${esc(sourceLabel)} ${icon('arrow-right')} ${esc(targetLabel)}</div>` : ui`<span class="detail-type">${esc(pretty(node?.type || 'concept'))}</span>`}<p class="muted detail-description">${esc(selected.origin === 'local' ? t(selected.description || 'No description was supplied for this item.') : selected.description || t('No description was supplied for this item.'))}</p><div class="provenance">${icon('info')}<span>${selected.origin === 'local' ? t('Document structure / keyword grouping') : selected.origin === 'annotation' ? t('Explicit author annotation') : selected.origin === 'ragflow' ? t('Machine-extracted · verify before relying on it') : t('Imported · verify before relying on it')}</span></div><div class="inspector-section"><div class="section-label">SOURCE DOCUMENTS <span>${selected.source_documents.length}</span></div>${selected.source_documents.map(id => { const doc = docs.find(d => d.id === id); return doc ? ui`<button class="source-card" data-doc="${esc(id)}">${icon('file-text')}<span>${esc(doc.name)}<small>Open source excerpts</small></span>${icon('arrow-up-right')}</button>` : ''; }).join('') || ui`<p class="muted small">No source document could be resolved. This relationship has no verified citation here.</p>`}${selected.source_refs?.length ? ui`<p class="muted small">${selected.source_refs.length} supplied source reference(s).</p>` : ''}</div>${linked.length ? ui`<div class="inspector-section"><div class="section-label">CONNECTIONS <span>${linked.length}</span></div>${linked.slice(0, 12).map(e => ui`<button class="connection-row" data-edge="${esc(e.id)}"><span>${esc(edgeLabel(e))}<strong>${esc(graph.nodes.find(n => n.id === (e.source === selected?.id ? e.target : e.source))?.label)}</strong></span>${icon('chevron-right')}</button>`).join('')}</div>` : ''}`;
}

function graphActions() {
  return ui`<div class="inspector-section"><div class="section-label">GRAPH TOOLS</div><button class="text-button" id="download-template">${icon('file-json')} Download JSON template</button>${kb()?.backend === 'ragflow' && config.legacy_graph_api ? ui`<button class="button secondary full" id="build-graph">${icon('wand-sparkles')} Build in RAGFlow</button><button class="text-button" id="sync-graph">${icon('refresh-cw')} Fetch graph & status</button>` : ''}${graph.origin !== 'local' ? ui`<button class="text-button" id="reset-graph">Return to document/topic map</button>` : ''}${graph.status === 'processing' ? ui`<p class="muted small">Graph construction is running. Fetch status to check progress.</p>` : ''}${graph.error ? ui`<p class="inline-error">${esc(graph.error)}</p>` : ''}</div>`;
}

function documentsView() {
  return ui`<div class="documents-layout"><section><div class="section-heading"><div><h2>Source library</h2><p class="muted small">The original documents behind your knowledge.</p></div><span class="small-badge">${docs.length} files</span></div><div class="upload-zone" id="drop-zone" tabindex="0" role="button" aria-label="Upload documents">${icon('cloud-upload')}<div><strong>Drop documents here, or <span>browse files</span></strong><p>Markdown, TXT, PDF, DOCX · up to 20 MB per file</p></div>${icon('arrow-up-right')}</div><div class="document-list">${docs.length ? docs.map(d => ui`<article class="document-card"><span class="file-icon">${icon('file-text')}</span><div class="document-info"><button class="doc-name" data-doc="${esc(d.id)}">${esc(d.name)}</button><div class="document-meta">${formatSize(d.size)}<span>·</span>${d.chunk_count} chunks${d.status === 'processing' ? ui`<span>·</span>${Math.round(d.progress * 100)}%` : ''}</div>${d.error ? ui`<p class="inline-error">${esc(t(d.error))}</p>` : ''}<div class="doc-topics">${d.topics.slice(0, 3).map(t => ui`<span>${esc(t)}</span>`).join('')}</div></div><span class="status-pill ${esc(d.status)}"><span></span>${esc(pretty(d.status))}</span>${['failed', 'unstarted'].includes(d.status) ? ui`<button class="icon-button" data-retry="${esc(d.id)}" aria-label="Retry ${esc(d.name)}">${icon('rotate-cw')}</button>` : ''}<button class="icon-button remove-doc" data-delete="${esc(d.id)}" aria-label="Remove ${esc(d.name)}" ${['queued', 'processing'].includes(d.status) ? 'disabled' : ''}>${icon('trash-2')}</button></article>`).join('') : empty('files', t('Start with a source'), t('Upload a document to make its text searchable and reveal its topics.'))}</div></section><aside class="topic-panel"><div class="section-heading"><h2>Organized by topic</h2>${icon('list-tree')}</div><p class="muted small">Topics come from headings, references, and frequent keywords.</p>${topics.map(t => ui`<button class="topic-card" data-topic="${esc(t.label)}">${icon('hash')}<div><strong>${esc(t.label)}</strong><small>${t.documents.length} document${getLanguage() === 'zh-CN' || t.documents.length === 1 ? '' : 's'}</small></div>${icon('chevron-right')}</button>`).join('') || ui`<p class="muted">No topics yet.</p>`}</aside></div>`;
}

function searchView() {
  return ui`<section class="search-page"><div class="search-intro"><span class="eyebrow">FIND THE EVIDENCE</span><h2>A question is a good place to start.</h2><p class="muted">Search across your documents and follow the source.</p></div><form id="search-form" class="search-box">${icon('search')}<input id="search-query" value="${esc(query)}" placeholder="Who leads Project Atlas?" aria-label="Search your documents" required maxlength="1000"><button class="button primary" ${searchBusy ? 'disabled' : ''}>${searchBusy ? t('Searching…') : t('Search')}${icon('arrow-right')}</button></form><div class="search-mode">${icon('info')} ${kb()?.backend === 'ragflow' ? t('Semantic retrieval through RAGFlow') : t('Local keyword retrieval')} · Results are source excerpts.</div>${!lastSearch ? ui`<div class="suggestions"><span>TRY A SEARCH</span>${(getLanguage() === 'zh-CN' ? ['知识图谱', '张伟', 'RAGFlow'] : ['Alice', 'RAGFlow', 'Source evidence']).map(q => ui`<button class="suggestion" data-query="${q}">${q}${icon('arrow-up-right')}</button>`).join('')}</div>` : ui`<div class="results-heading"><strong>${results.length} results</strong><span>for “${esc(lastSearch)}” · ${esc(t(searchMode))} retrieval</span></div><div class="search-results">${results.length ? results.map((r, i) => ui`<article class="result-card"><div class="result-source"><span class="result-number">${String(i + 1).padStart(2, '0')}</span>${icon('file-text')}<button ${r.doc_id ? `data-doc="${esc(r.doc_id)}"` : 'disabled'}>${esc(r.document_name)}</button><span>${r.page ? t('Page {count}', {count:r.page}) : r.ordinal ? t('Chunk {count}', {count:r.ordinal}) : t('Retrieved excerpt')}</span></div><p>${highlight(r.content, query)}</p>${r.doc_id ? ui`<button class="text-button" data-doc="${esc(r.doc_id)}">Open source ${icon('arrow-up-right')}</button>` : ui`<span class="muted small">Refresh to resolve this source document.</span>`}</article>`).join('') : empty('search', t('No matching excerpts'), t('Try a different keyword, or add a document that covers this question.'))}</div>`}</section>`;
}

function drawGraph() {
  const container = document.getElementById('graph-canvas');
  if (!container) return;
  const elements: ElementDefinition[] = [...graph.nodes.map(n => ({ data: { ...n, color: palette[n.type]?.color || palette.concept.color, border: palette[n.type]?.border || palette.concept.border, size: n.type === 'document' ? 34 : 44 } })), ...graph.edges.map(e => ({ data: { ...e, label: e.relation }, classes: e.origin === 'local' ? 'structural' : 'semantic' }))];
  cy = cytoscape({
    container, elements, minZoom: 0.2, maxZoom: 3,
    style: [
      { selector: 'node', style: { 'background-color': 'data(color)', 'border-color': 'data(border)', 'border-width': 1.5, width: 'data(size)', height: 'data(size)', label: 'data(label)', color: '#33463f', 'font-family': '-apple-system, PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif', 'font-size': 11, 'font-weight': 500, 'text-valign': 'bottom', 'text-margin-y': 8, 'text-wrap': 'wrap', 'text-max-width': '110px', 'text-background-color': '#fafbf9', 'text-background-opacity': 0.85, 'text-background-padding': '2px' } },
      { selector: 'node[type="document"]', style: { shape: 'round-rectangle' } },
      { selector: 'edge', style: { width: 1.2, 'line-color': '#cbd5ce', 'target-arrow-color': '#acbcb1', 'curve-style': 'bezier', 'font-size': 9, color: '#73847a', 'text-background-color': '#fafbf9', 'text-background-opacity': 1, 'text-background-padding': '3px', 'text-rotation': 'autorotate' } },
      { selector: 'edge.semantic', style: { 'target-arrow-shape': 'triangle', 'line-color': '#9bad9e', label: 'data(label)' } },
      { selector: '.dimmed', style: { opacity: 0.12 } },
      { selector: ':selected', style: { 'border-width': 3, 'border-color': '#365d4c', 'line-color': '#365d4c', 'target-arrow-color': '#365d4c', width: 3 } },
      { selector: 'node:selected', style: { width: 48, height: 48 } },
      { selector: '.hidden', style: { display: 'none' } },
    ],
    layout: { name: 'concentric', animate: false, fit: false, padding: 55, concentric: n => n.degree(), levelWidth: () => 2, minNodeSpacing: 65, equidistant: true, avoidOverlap: true },
  });
  cy.on('tap', 'node, edge', event => {
    const id = event.target.id();
    selected = graph.nodes.find(n => n.id === id) || graph.edges.find(e => e.id === id);
    updateInspector(); focusSelected();
  });
  cy.on('tap', event => { if (event.target === cy) { selected = undefined; updateInspector(); focusSelected(); } });
  applyGraphFilter();
  if (selected) { cy.getElementById(selected.id).select(); focusSelected(); }
  if (cy.nodes().length <= 60) {
    // Place the most connected idea in the center; spread its neighbors on two rings.
    const ordered = cy.nodes().sort((a, b) => b.degree() - a.degree());
    const remainder = ordered.length - 1;
    const innerCount = remainder > 12 ? Math.ceil(remainder / 3) : 0;
    ordered.forEach((n, i) => {
      if (i === 0) { n.position({ x: 0, y: 0 }); return; }
      const inner = i <= innerCount;
      const count = inner ? innerCount : remainder - innerCount;
      const index = inner ? i - 1 : i - 1 - innerCount;
      const angle = -Math.PI / 2 + index * 2 * Math.PI / count + (inner ? 0 : Math.PI / count);
      const radius = inner ? 100 : 205;
      n.position({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
    });
  }
  fitGraph();
  const observer = new ResizeObserver(() => { cy?.resize(); fitGraph(); });
  observer.observe(container);
  cy.on('destroy', () => observer.disconnect());
  on('#zoom-in', 'click', () => zoom(1.25)); on('#zoom-out', 'click', () => zoom(0.8));
  on('#fit', 'click', fitGraph);
  on('#layout', 'click', () => { cy?.layout({ name: 'cose', animate: false, padding: 55 }).run(); fitGraph(); });
}
function fitGraph() {
  if (!cy || !cy.nodes(':visible').length) return;
  const nodes = cy.nodes(':visible');
  if (nodes.length > 60 || cy.width() < 450) { cy.fit(cy.elements(':visible'), cy.width() < 450 ? 20 : 45); return; }
  // Keep labels readable on small maps by fitting node positions at a 1:1 zoom.
  const points = nodes.map(n => n.position());
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min(Math.max(100, cy.width() - 170) / Math.max(1, maxX - minX), Math.max(100, cy.height() - 150) / Math.max(1, maxY - minY));
  const centerX = (minX + maxX) / 2, centerY = (minY + maxY) / 2;
  nodes.positions(n => ({ x: (n.position('x') - centerX) * scale + cy!.width() / 2, y: (n.position('y') - centerY) * scale + cy!.height() / 2 - 5 }));
  cy.zoom(1); cy.pan({ x: 0, y: 0 });
}
function zoom(factor: number) { if (cy) cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
function applyGraphFilter() {
  if (!cy) return;
  cy.nodes().forEach(n => { n.toggleClass('hidden', typeFilters.has(n.data('type'))); });
  cy.edges().forEach(e => { e.toggleClass('hidden', typeFilters.has(e.source().data('type')) || typeFilters.has(e.target().data('type'))); });
  focusSelected();
  const count = document.getElementById('graph-count');
  if (count) count.textContent = t('{nodes} nodes · {edges} connections', {nodes:cy.nodes(':visible').length, edges:cy.edges(':visible').length});
}
function focusSelected() {
  if (!cy) return;
  cy.elements().removeClass('dimmed');
  if (graphFilter) {
    const matches = cy.nodes().filter(n => n.data('label').toLowerCase().includes(graphFilter.toLowerCase()));
    cy.elements().addClass('dimmed'); matches.closedNeighborhood().removeClass('dimmed');
  } else if (selected) {
    cy.elements().addClass('dimmed');
    const element = cy.getElementById(selected.id);
    const related = 'relation' in selected ? element.union(element.connectedNodes()) : element.closedNeighborhood();
    related.removeClass('dimmed');
  }
}
function updateInspector() {
  const panel = document.getElementById('inspector');
  if (panel) { panel.innerHTML = inspector(); bindInspector(); drawIcons(); }
}

function bindInspector() {
  app.querySelectorAll<HTMLElement>('#inspector [data-doc]').forEach(el => el.addEventListener('click', () => withError(() => showDoc(el.dataset.doc!))));
  app.querySelectorAll<HTMLElement>('#inspector [data-topic]').forEach(el => el.addEventListener('click', () => selectTopic(el.dataset.topic!)));
  app.querySelectorAll<HTMLElement>('[data-edge]').forEach(el => el.addEventListener('click', () => {
    selected = graph.edges.find(e => e.id === el.dataset.edge); cy?.elements().unselect(); cy?.getElementById(el.dataset.edge!).select(); updateInspector(); focusSelected();
  }));
  on('#clear-selection', 'click', () => { selected = undefined; cy?.elements().unselect(); updateInspector(); focusSelected(); });
  on('#download-template', 'click', () => downloadJSON('graph-template.json', {
    nodes: [{ id: 'alice', label: 'Alice Chen', type: 'person', description: 'Project lead', source_documents: docs[0] ? [docs[0].id] : [] }, { id: 'atlas', label: 'Project Atlas', type: 'project' }],
    edges: [{ source: 'alice', target: 'atlas', relation: 'leads', description: 'Replace this with source evidence.', source_documents: docs[0] ? [docs[0].id] : [] }],
  }));
  on('#reset-graph', 'click', () => withError(async () => { await api(`${baseURL()}/graph/import`, { method: 'DELETE' }); selected = undefined; await refresh(); toast(t('Document/topic map restored.')); }));
  on('#build-graph', 'click', () => withError(async () => { await post(`${baseURL()}/graph/build`); await refresh(); toast(t('Graph construction started in RAGFlow.')); }));
  on('#sync-graph', 'click', () => withError(async () => { const result = await post<{ status: string }>(`${baseURL()}/graph/sync`); await refresh(); toast(result.status === 'ready' ? t('Graph refreshed.') : t('Graph is still processing or not available yet.')); }));
}

function bind() {
  app.querySelectorAll<HTMLElement>('[data-base]').forEach(el => el.addEventListener('click', () => withError(async () => {
    current = el.dataset.base!; selected = undefined; query = ''; results = []; lastSearch = ''; graphFilter = ''; typeFilters.clear(); searchVersion++; searchBusy = false; await refresh();
  })));
  app.querySelectorAll<HTMLElement>('[data-view]').forEach(el => el.addEventListener('click', () => { view = el.dataset.view as View; render(); }));
  on('#language-toggle', 'click', () => { setLanguage(getLanguage() === 'zh-CN' ? 'en' : 'zh-CN'); render(); });
  on('#home-workspace', 'click', () => { view = 'graph'; render(); });
  on('#add-base', 'click', createBaseDialog); on('#empty-create', 'click', createBaseDialog);
  on('#settings', 'click', settingsDialog); on('#connection-badge', 'click', settingsDialog);
  on('#upload-button', 'click', () => document.getElementById('upload-input')?.click());
  on('#upload-input', 'change', event => withError(() => uploadFiles((event.target as HTMLInputElement).files)));
  on('#drop-zone', 'click', () => document.getElementById('upload-input')?.click());
  on('#drop-zone', 'keydown', event => { if (['Enter', ' '].includes((event as KeyboardEvent).key)) { event.preventDefault(); document.getElementById('upload-input')?.click(); } });
  on('#drop-zone', 'dragover', event => { event.preventDefault(); (event.currentTarget as HTMLElement).classList.add('dragging'); });
  on('#drop-zone', 'dragleave', event => (event.currentTarget as HTMLElement).classList.remove('dragging'));
  on('#drop-zone', 'drop', event => { event.preventDefault(); withError(() => uploadFiles((event as DragEvent).dataTransfer?.files || null)); });
  on('#sync', 'click', () => withError(sync));
  app.querySelectorAll<HTMLElement>('.view [data-doc]').forEach(el => { if (!el.closest('#inspector')) el.addEventListener('click', () => withError(() => showDoc(el.dataset.doc!))); });
  app.querySelectorAll<HTMLElement>('.view [data-topic]').forEach(el => { if (!el.closest('#inspector')) el.addEventListener('click', () => selectTopic(el.dataset.topic!)); });
  app.querySelectorAll<HTMLElement>('[data-retry]').forEach(el => el.addEventListener('click', () => withError(async () => { await post(`${baseURL()}/documents/${el.dataset.retry}/retry`); await refresh(); toast(t('Processing restarted.')); })));
  app.querySelectorAll<HTMLElement>('[data-delete]').forEach(el => el.addEventListener('click', () => deleteDialog(el.dataset.delete!)));
  on('#graph-filter', 'input', event => {
    graphFilter = (event.target as HTMLInputElement).value; focusSelected();
    const matches = graph.nodes.filter(n => n.label.toLowerCase().includes(graphFilter.toLowerCase())).slice(0, 6);
    const panel = app.querySelector<HTMLElement>('#node-results')!;
    panel.hidden = !graphFilter.trim();
    panel.innerHTML = matches.map(n => ui`<button data-node="${esc(n.id)}">${icon('circle')}<span>${esc(n.label)}</span><small>${esc(pretty(n.type))}</small></button>`).join('') || ui`<p>No matching nodes.</p>`;
    panel.querySelectorAll<HTMLElement>('[data-node]').forEach(el => el.addEventListener('click', () => {
      selected = graph.nodes.find(n => n.id === el.dataset.node); graphFilter = ''; (app.querySelector('#graph-filter') as HTMLInputElement).value = ''; panel.hidden = true;
      cy?.elements().unselect(); cy?.getElementById(el.dataset.node!).select(); updateInspector(); focusSelected();
    }));
    drawIcons();
  });
  app.querySelectorAll<HTMLElement>('[data-type]').forEach(el => el.addEventListener('click', () => {
    const type = el.dataset.type!; typeFilters.has(type) ? typeFilters.delete(type) : typeFilters.add(type); el.classList.toggle('off', typeFilters.has(type)); applyGraphFilter();
  }));
  on('#import-graph', 'click', () => document.getElementById('graph-input')?.click());
  on('#graph-input', 'change', event => withError(async () => {
    const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return;
    const form = new FormData(); form.append('file', file);
    await api(`${baseURL()}/graph/import`, { method: 'POST', body: form }); selected = undefined; typeFilters.clear(); graphFilter = ''; await refresh(); toast(t('Graph imported. Inspect sources to verify relationships.'));
  }));
  on('#export-graph', 'click', () => downloadJSON('atlas-graph.json', graph));
  on('#search-query', 'input', event => query = (event.target as HTMLInputElement).value);
  on('#search-form', 'submit', event => { event.preventDefault(); withError(runSearch); });
  app.querySelectorAll<HTMLElement>('[data-query]').forEach(el => el.addEventListener('click', () => { query = el.dataset.query!; withError(runSearch); }));
  bindInspector();
}

function selectTopic(label: string) {
  view = 'graph'; graphFilter = ''; typeFilters.clear(); selected = graph.nodes.find(n => n.label === label);
  render(); if (selected && cy) cy.animate({ center: { eles: cy.getElementById(selected.id) } }, { duration: 250 });
}
async function uploadFiles(files: FileList | null) {
  if (!files?.length) return;
  const url = baseURL();
  let added = 0;
  for (const file of Array.from(files)) {
    try {
      if (file.size > config.max_upload_mb * 1024 * 1024) throw new Error(`${file.name}: exceeds ${config.max_upload_mb} MB.`);
      const form = new FormData(); form.append('file', file);
      await api(`${url}/documents`, { method: 'POST', body: form }); added++;
    } catch (e) { toast((e as Error).message, true); }
  }
  if (added) { view = 'documents'; await refresh(); toast(t('Added {count} documents. Processing starts automatically.', {count:added})); }
}
async function sync() {
  if (syncBusy) return;
  syncBusy = true; render();
  try { await post(`${baseURL()}/sync`); await refresh(); toast(t('Workspace refreshed.')); }
  finally { syncBusy = false; render(); }
}
async function runSearch() {
  if (!query.trim()) return;
  const version = ++searchVersion, question = query.trim(), url = baseURL();
  searchBusy = true; render();
  try {
    const response = await post<{ mode: string; results: Chunk[] }>(`${url}/search`, { question });
    if (version !== searchVersion) return;
    results = response.results; searchMode = response.mode; lastSearch = question;
  } finally { if (version === searchVersion) { searchBusy = false; render(); document.getElementById('search-query')?.focus(); } }
}

function dialog(title: string, body: string, wide = false) {
  document.querySelector('dialog')?.remove();
  const el = document.createElement('dialog'); el.className = `dialog ${wide ? 'wide' : ''}`;
  el.innerHTML = ui`<div class="dialog-heading"><h2>${esc(title)}</h2><button class="icon-button close-dialog" aria-label="Close dialog">${icon('x')}</button></div>${body}`;
  document.body.appendChild(el); el.showModal();
  el.querySelector('.close-dialog')?.addEventListener('click', () => el.close());
  el.addEventListener('click', event => { if (event.target === el) { const r = el.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) el.close(); } });
  el.addEventListener('close', () => el.remove()); drawIcons();
  return el;
}
async function showDoc(id: string) {
  const doc = await api<Doc>(`${baseURL()}/documents/${encodeURIComponent(id)}`);
  const el = dialog(doc.name, ui`<div class="document-preview-meta"><span class="status-pill ${esc(doc.status)}">${esc(pretty(doc.status))}</span><span>${doc.chunks?.length || 0} chunks</span><a class="text-button" href="${baseURL()}/documents/${encodeURIComponent(id)}/download" download>${icon('download')} Original file</a></div>${doc.error ? ui`<p class="inline-error">${esc(t(doc.error))}</p>` : ''}<div class="chunk-list">${doc.chunks?.map(c => ui`<article class="chunk-card" id="chunk-${esc(c.id)}"><div class="section-label">CHUNK ${c.ordinal}${c.page ? (getLanguage() === 'zh-CN' ? ` · 页码 ${c.page}` : ` · PAGE ${c.page}`) : ''}<span class="chunk-id">${c.id.slice(0, 8)}</span></div><pre>${esc(c.content)}</pre></article>`).join('') || ui`<p class="muted">No chunks yet. Refresh processing status or retry this document.</p>`}</div>`, true);
  if (selected && 'source_chunks' in selected && selected.source_chunks?.length) {
    const target = el.querySelector(`#chunk-${CSS.escape(selected.source_chunks[0])}`);
    target?.classList.add('evidence-chunk'); target?.scrollIntoView({ block: 'center' });
  }
}
function createBaseDialog() {
  const el = dialog(t('Create a knowledge base'), ui`<p class="muted">Keep a project’s documents and connections together.</p><form id="create-form"><label>Name<input name="name" placeholder="e.g. Product research" required maxlength="100" autofocus></label><label>Description<textarea name="description" placeholder="What belongs in this workspace?" maxlength="1000" rows="2"></textarea></label><label>Knowledge engine<select name="backend"><option value="local">Local · works without credentials</option><option value="ragflow" ${!config.ragflow_configured ? 'disabled' : ''}>RAGFlow · parsing and semantic retrieval</option></select></label>${!config.ragflow_configured ? ui`<p class="muted small">To enable RAGFlow, configure the connection in .env and restart the server.</p>` : ''}<label id="dataset-field" hidden>Existing RAGFlow dataset ID (optional)<input name="dataset_id" placeholder="Leave blank to create a new dataset"></label><p class="inline-error" id="form-error" role="alert"></p><button class="button primary full" type="submit">Create knowledge base ${icon('arrow-right')}</button></form>`);
  el.querySelector('select')?.addEventListener('change', event => { (el.querySelector('#dataset-field') as HTMLElement).hidden = (event.target as HTMLSelectElement).value !== 'ragflow'; });
  el.querySelector('form')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = new FormData(event.target as HTMLFormElement), button = el.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    button.disabled = true;
    try {
      const created = await post<KB>('/api/knowledge-bases', { name: form.get('name'), description: form.get('description'), backend: form.get('backend'), dataset_id: form.get('dataset_id') || null });
      current = created.id; selected = undefined; query = ''; results = []; lastSearch = ''; graphFilter = ''; typeFilters.clear(); searchVersion++; searchBusy = false; view = 'documents'; el.close(); await refresh(); toast(t('Knowledge base created.'));
    } catch (e) { el.querySelector('#form-error')!.textContent = t((e as Error).message); }
    finally { button.disabled = false; }
  });
}
function deleteDialog(id: string) {
  const doc = docs.find(d => d.id === id); if (!doc) return;
  const el = dialog(t('Remove document?'), ui`<p class="muted">Remove <strong>${esc(doc.name)}</strong> and its chunks from this knowledge base${kb()?.backend === 'ragflow' ? ' and the connected RAGFlow dataset' : ''}. Any imported graph will be cleared to avoid stale source references.</p><button class="button danger full" id="confirm-delete">Remove document</button><p class="inline-error" id="delete-error"></p>`);
  el.querySelector<HTMLButtonElement>('#confirm-delete')!.addEventListener('click', async event => {
    const button = event.currentTarget as HTMLButtonElement; button.disabled = true;
    try { await api(`${baseURL()}/documents/${id}`, { method: 'DELETE' }); selected = undefined; el.close(); await refresh(); toast(t('Document removed.')); }
    catch (e) { el.querySelector('#delete-error')!.textContent = (e as Error).message; button.disabled = false; }
  });
}
function settingsDialog() {
  dialog(t('Connections & help'), ui`<div class="connection-status">${icon('plug')}<div><strong>RAGFlow</strong><p>${config.ragflow_configured ? t('Configured on the backend') : t('No connection configured')}</p></div><span class="status-dot ${config.ragflow_configured ? '' : 'inactive'}"></span></div>
  <p class="muted">Atlas organizes and displays your knowledge; RAGFlow is the engine that parses and retrieves documents. Think of Atlas as the dashboard, and RAGFlow as a separate search engine behind it.</p>
  <div class="help-block"><h3>1. Prepare a RAGFlow service</h3><p>On Ubuntu 24.04 x86-64, install the native stack from the Linux release. It runs RAGFlow, MySQL, Redis, Elasticsearch, and MinIO as system services, without containers. Open the RAGFlow UI through an SSH tunnel.</p><pre>sudo ./scripts/install-ragflow-native.sh --install</pre><p>RAGFlow UI: http://127.0.0.1:8080 · Atlas: http://127.0.0.1:8000</p></div>
  <div class="help-block"><h3>2. Set models and get the API key</h3><p>In RAGFlow, open Model providers and configure an embedding model that supports Chinese. Then open your avatar → API and create an API key. This is the RAGFlow key, not the model provider key.</p></div>
  <div class="help-block"><h3>3. Fill in Atlas’s connection settings</h3><p>On Linux, edit deploy/atlas.env. For local development, copy .env.example to .env. Use the URL that actually reaches your RAGFlow API, not Atlas’s own address:</p><pre>RAGFLOW_BASE_URL=http://127.0.0.1:9380
RAGFLOW_API_KEY=your-ragflow-api-key</pre></div>
  <div class="help-block"><h3>4. Check, restart, and create a knowledge base</h3><p>Run scripts/check-ragflow.sh. Restart Atlas, then create a knowledge base with the RAGFlow engine. Upload a document and press Refresh until it is ready. Existing local workspaces stay local.</p><pre>./scripts/check-ragflow.sh
sudo systemctl restart atlas</pre></div>
  <div class="help-block"><h3>Make explicit connections</h3><p>In Markdown or TXT, annotate a relationship like this:</p><pre>${getLanguage() === 'zh-CN' ? '[[张伟]] --负责--> [[知识图谱项目]]' : '[[Alice Chen]] --leads--> [[Project Atlas]]'}</pre><p>Select that edge in the graph to open the supporting text.</p></div>
  <div class="help-block"><h3>Import an entity graph</h3><p>Build a graph artifact in RAGFlow, or use a graph you already have. Import a JSON object containing <code>nodes</code> and <code>edges</code>. Download the template from the graph explorer.</p><p>The MVP supports legacy graph endpoints when <code>RAGFLOW_LEGACY_GRAPH_API=true</code>. Newer servers may require JSON artifact imports.</p></div><p class="muted small">This is a single-user local MVP. A shared deployment needs authentication and access controls.</p>`, true);
}
function downloadJSON(name: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function start() {
  app.innerHTML = ui`<div class="loading-screen">Opening your knowledge workspace…</div>`;
  try { config = await api<Config>('/api/config'); await refresh(); }
  catch (e) { app.innerHTML = ui`<div class="loading-screen"><h2>Could not open the workspace</h2><p>${esc((e as Error).message)}</p><button id="reload" class="button primary">Try again</button></div>`; on('#reload', 'click', () => { void start(); }); }
}
void start();
window.setInterval(() => {
  if (!document.querySelector('dialog') && !syncBusy && docs.some(d => d.status === 'queued')) void refresh().catch(() => {});
}, 2500);
