export function highlight(content: string, query: string): string {
  const escapeHTML = (text: string) => text.replace(/[&<>"']/g, char =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]!));
  const terms = query.match(/[a-zA-Z0-9_-]{3,}|[\u4e00-\u9fff]{2,}/g) || [];
  const patterns = [...new Set(terms)].sort((a, b) => b.length - a.length).map(term =>
    /^[\u4e00-\u9fff]+$/.test(term) ? term : `\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
  if (!patterns.length) return escapeHTML(content);
  const matcher = new RegExp(`(${patterns.join('|')})`, 'gi');
  return content.split(matcher).map((part, i) => i % 2 ? `<mark>${escapeHTML(part)}</mark>` : escapeHTML(part)).join('');
}
