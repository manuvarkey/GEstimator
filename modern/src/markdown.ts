/** Minimal, safe Markdown to HTML for author notes: headings, bold, italics,
 * inline code, lists, quotes, rules, links (http/https only) and paragraphs.
 * All text is HTML-escaped before formatting, so notes cannot inject markup. */
function escape(text: string) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function inline(text: string) {
  const codes: string[] = [];
  let html = escape(text).replace(/`([^`]+)`/g, (_, code) => `\u0000${codes.push(code) - 1}\u0000`);
  html = html
    .replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, (_, a, b) => `<strong>${a ?? b}</strong>`)
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/(^|[^\w_])_([^_\s][^_]*)_(?!\w)/g, "$1<em>$2</em>")
    .replace(/~~([^~]+)~~/g, "<del>$1</del>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return html.replace(/\u0000(\d+)\u0000/g, (_, index) => `<code>${codes[Number(index)]}</code>`);
}

export function renderMarkdown(source: string) {
  const out: string[] = [];
  let list: "ul" | "ol" | undefined;
  let paragraph: string[] = [];
  let fence: string[] | undefined;
  const flush = () => {
    if (paragraph.length) out.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
    paragraph = [];
  };
  const closeList = () => { if (list) out.push(`</${list}>`); list = undefined; };
  for (const raw of source.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    if (fence) {
      if (/^```/.test(line)) { out.push(`<pre><code>${escape(fence.join("\n"))}</code></pre>`); fence = undefined; }
      else fence.push(raw);
      continue;
    }
    if (/^```/.test(line)) { flush(); closeList(); fence = []; continue; }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (!line.trim()) { flush(); closeList(); }
    else if (heading) { flush(); closeList(); out.push(`<h${heading[1]!.length}>${inline(heading[2]!)}</h${heading[1]!.length}>`); }
    else if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) { flush(); closeList(); out.push("<hr>"); }
    else if (/^>\s?/.test(line)) { flush(); closeList(); out.push(`<blockquote>${inline(line.replace(/^>\s?/, ""))}</blockquote>`); }
    else if (bullet || numbered) {
      flush();
      const kind = bullet ? "ul" : "ol";
      if (list !== kind) { closeList(); out.push(`<${kind}>`); list = kind; }
      out.push(`<li>${inline((bullet ?? numbered)![1]!)}</li>`);
    } else { closeList(); paragraph.push(line); }
  }
  if (fence) out.push(`<pre><code>${escape(fence.join("\n"))}</code></pre>`);
  flush();
  closeList();
  return out.join("");
}
