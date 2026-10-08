import chinese from './zh-CN.json' with { type: 'json' };

export type Language = 'zh-CN' | 'en';
let language: Language = localStorage.getItem('atlas.language') === 'en' ? 'en' : 'zh-CN';
const translations: Record<string, string> = chinese;

export const getLanguage = () => language;
export function setLanguage(value: Language) {
  language = value;
  localStorage.setItem('atlas.language', value);
  document.documentElement.lang = value;
  document.title = value === 'zh-CN' ? 'Atlas — 知识工作区' : 'Atlas — Knowledge workspace';
}

export function t(message: string, values: Record<string, string | number> = {}): string {
  const text = language === 'zh-CN' ? translations[message] || message : message;
  return text.replace(/\{(\w+)\}/g, (match, key) => String(values[key] ?? match));
}

const keys = Object.keys(translations).sort((a, b) => b.length - a.length);
const matcher = new RegExp(keys.map(key => key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
function translateLiteral(literal: string): string {
  if (language === 'en') return literal;
  // Only translate static interface text and labels. Interpolated document
  // contents, user names, graph labels, IDs, URLs, and code remain untouched.
  return literal.replace(/(^|>)([^<]*)(?=<|$)/g, (_match, prefix, text: string) =>
    prefix + text.replace(matcher, match => translations[match]))
    .replace(/\b(aria-label|placeholder|title)="([^"]*)"/g,
      (_match, attribute, value) => `${attribute}="${t(value)}"`);
}

export function ui(parts: TemplateStringsArray, ...values: unknown[]): string {
  return parts.map((part, i) => translateLiteral(part) + (i < values.length ? String(values[i] ?? '') : '')).join('');
}
setLanguage(language);
