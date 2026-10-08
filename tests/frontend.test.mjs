import test from 'node:test';
import assert from 'node:assert/strict';

const memory = new Map();
globalThis.localStorage = {getItem:key=>memory.get(key)??null,setItem:(key,value)=>memory.set(key,value)};
globalThis.document = {documentElement:{lang:''},title:''};
const {ui,t,setLanguage,getLanguage} = await import('../frontend/i18n.ts');
const {highlight} = await import('../frontend/highlight.ts');

test('Chinese UI preserves document contents, IDs, and CSS classes', () => {
  setLanguage('zh-CN');
  const source = 'Search documents <untrusted>';
  const html = ui`<button class="document-card" data-id="${'Search'}" aria-label="Search your documents">Search</button><pre>${source}</pre>`;
  assert.match(html,/class="document-card"/);
  assert.match(html,/data-id="Search"/);
  assert.match(html,/aria-label="搜索文档内容"/);
  assert.match(html,/>搜索<\/button>/);
  assert.ok(html.includes(source));
});
test('language switching persists and updates page language', () => {
  setLanguage('en');
  assert.equal(t('Search'),'Search');
  assert.equal(ui`<button>Search</button>`,'<button>Search</button>');
  assert.equal(memory.get('atlas.language'),'en');
  setLanguage('zh-CN');
  assert.equal(getLanguage(),'zh-CN');
  assert.equal(document.documentElement.lang,'zh-CN');
  assert.equal(t('Page {count}',{count:3}),'第 3 页');
});
test('Chinese highlights do not introduce HTML from the document', () => {
  assert.equal(highlight('张伟负责知识图谱。<script>','知识图谱'), '张伟负责<mark>知识图谱</mark>。&lt;script&gt;');
  assert.equal(highlight('&amp; SCRIPT','script'), '&amp;amp; <mark>SCRIPT</mark>');
});
