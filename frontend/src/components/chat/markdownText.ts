/**
 * Markdown der Antworten vorbereiten, rein und ohne React:
 * - splitBlocks: Text in Absaetze teilen, damit beim Streamen nur der letzte Absatz neu gerendert wird.
 * - remarkPartTags: bekannte Kennzeichen im Fliesstext zu Links "part:<tag>" machen (die Antwort rendert sie als
 *   Knoepfe zum Bauteil). Code, Links und Belege bleiben unberuehrt.
 */

const FENCE = /^\s{0,3}(`{3,}|~{3,})/;
const LIST_ITEM = /^\s{0,3}([-*+]|\d{1,9}[.)])\s/;
const INDENTED = /^(\s{2,}|\t)\S/;

/** Teilt an Leerzeilen; Codebloecke und lose Listen (Leerzeile zwischen Punkten) bleiben ein Stueck. */
export function splitBlocks(markdown: string): string[] {
  const lines = markdown.split("\n");
  const blocks: string[] = [];
  let current: string[] = [];
  let fence: string | null = null;
  const flush = () => {
    const text = current.join("\n").trim();
    if (text) blocks.push(text);
    current = [];
  };
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const fenceMatch = line.match(FENCE);
    if (fence) {
      current.push(line);
      if (fenceMatch && fenceMatch[1][0] === fence[0] && fenceMatch[1].length >= fence.length) fence = null;
      continue;
    }
    if (fenceMatch) {
      fence = fenceMatch[1];
      current.push(line);
      continue;
    }
    if (line.trim() === "") {
      const next = lines.slice(i + 1).find((l) => l.trim() !== "");
      const listBlock = current.some((l) => LIST_ITEM.test(l));
      const continues = next !== undefined && current.length > 0 && listBlock && (LIST_ITEM.test(next) || INDENTED.test(next));
      if (continues) current.push(line);
      else flush();
      continue;
    }
    current.push(line);
  }
  flush();
  return blocks;
}

/** Minimaler mdast-Ausschnitt, den das Plugin braucht. */
export interface MdNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdNode[];
}

const SKIP = new Set(["link", "linkReference", "inlineCode", "code", "html", "definition", "image", "imageReference"]);

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Treffermuster fuer die Kennzeichen; laengste zuerst, nicht mitten im Wort und nicht als Teil von -X1:5 oder E0.3. */
export function tagPattern(tags: string[]): RegExp | null {
  const unique = [...new Set(tags.map((t) => t.trim()).filter(Boolean))].sort((a, b) => b.length - a.length);
  if (unique.length === 0) return null;
  return new RegExp(`(?<![\\w])(${unique.map(escapeRegExp).join("|")})(?![\\w]|[:.]\\w)`, "gi");
}

export const PART_SCHEME = "part:";

export function partHref(tag: string): string {
  return `${PART_SCHEME}${encodeURIComponent(tag)}`;
}

export function tagFromHref(href: string | undefined): string | null {
  if (!href?.startsWith(PART_SCHEME)) return null;
  try {
    return decodeURIComponent(href.slice(PART_SCHEME.length));
  } catch {
    return null;
  }
}

function splitText(value: string, pattern: RegExp, canonical: Map<string, string>): MdNode[] {
  const out: MdNode[] = [];
  let last = 0;
  pattern.lastIndex = 0;
  for (const match of value.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > last) out.push({ type: "text", value: value.slice(last, start) });
    const tag = canonical.get(match[0].toLowerCase()) ?? match[0];
    out.push({ type: "link", url: partHref(tag), children: [{ type: "text", value: match[0] }] });
    last = start + match[0].length;
  }
  if (last === 0) return [{ type: "text", value }];
  if (last < value.length) out.push({ type: "text", value: value.slice(last) });
  return out;
}

function visit(node: MdNode, pattern: RegExp, canonical: Map<string, string>) {
  if (!node.children) return;
  const children: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value) children.push(...splitText(child.value, pattern, canonical));
    else {
      if (!SKIP.has(child.type)) visit(child, pattern, canonical);
      children.push(child);
    }
  }
  node.children = children;
}

/** remark-Plugin: Optionen { tags } aus meta.referenced_tags. */
export function remarkPartTags(options?: { tags?: string[] }) {
  const tags = options?.tags ?? [];
  const pattern = tagPattern(tags);
  const canonical = new Map(tags.map((t) => [t.trim().toLowerCase(), t.trim()]));
  return (tree: MdNode) => {
    if (pattern) visit(tree, pattern, canonical);
  };
}
