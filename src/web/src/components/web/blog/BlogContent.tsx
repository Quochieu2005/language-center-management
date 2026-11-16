import styles from "./BlogContent.module.scss";

type Block =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "ordered-list"; start: number; items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] };

function cells(line: string) {
  return line.trim().replace(/\\\|/g, "\uE000").replace(/^\||\|$/g, "")
    .split("|").map((cell) => cell.replace(/\uE000/g, "|").trim());
}

function isTable(lines: string[], index: number) {
  if (!lines[index]?.includes("|") || !lines[index + 1]?.includes("|")) return false;
  return cells(lines[index + 1]).every((cell) => /^:?-{3,}:?$/.test(cell));
}

export function addMarkdownTableRow(content: string, cursorPosition: number | null) {
  const normalizedContent = content.replace(/\r\n?/g, "\n");
  const lines = normalizedContent.split("\n");
  const lineStarts: number[] = [];
  let offset = 0;
  for (const line of lines) {
    lineStarts.push(offset);
    offset += line.length + 1;
  }

  const tables: { start: number; end: number; insertAt: number; columns: number }[] = [];
  for (let index = 0; index < lines.length - 1;) {
    if (!isTable(lines, index)) { index += 1; continue; }
    let insertAt = index + 2;
    while (insertAt < lines.length && lines[insertAt].trim() && lines[insertAt].includes("|")) insertAt += 1;
    tables.push({
      start: lineStarts[index],
      end: lineStarts[insertAt] ?? normalizedContent.length,
      insertAt,
      columns: cells(lines[index]).length,
    });
    index = insertAt;
  }
  if (!tables.length) return null;

  const table = tables.find(({ start, end }) => cursorPosition !== null && cursorPosition >= start && cursorPosition <= end)
    ?? tables[tables.length - 1];
  lines.splice(table.insertAt, 0, `| ${Array(table.columns).fill("Nội dung").join(" | ")} |`);
  return lines.join("\n");
}

function heading(line: string) {
  const match = /^(#{1,3})\s+(.+)$/.exec(line);
  return match ? { type: "heading" as const, level: match[1].length as 1 | 2 | 3, text: match[2] } : null;
}

function orderedItem(line: string) {
  const match = /^(\d+)[.)]\s+(.+)$/.exec(line);
  return match ? { number: Number(match[1]), text: match[2] } : null;
}

function parseContent(content: string): Block[] {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index += 1; continue; }

    const title = heading(line);
    if (title) { blocks.push(title); index += 1; continue; }

    const item = orderedItem(line);
    if (item) {
      const items: string[] = [];
      const start = item.number;
      while (index < lines.length) {
        const nextLine = lines[index].trim();
        const next = orderedItem(nextLine);
        if (next) {
          items.push(next.text);
          index += 1;
          continue;
        }
        if (!nextLine || heading(nextLine) || isTable(lines, index)) break;
        items[items.length - 1] += `\n${nextLine}`;
        index += 1;
      }
      blocks.push({ type: "ordered-list", start, items });
      continue;
    }

    if (isTable(lines, index)) {
      const headers = cells(lines[index]);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        rows.push(cells(lines[index]));
        index += 1;
      }
      blocks.push({ type: "table", headers, rows });
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim()
      && !heading(lines[index].trim()) && !orderedItem(lines[index].trim())
      && !isTable(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraph.join(" ") });
  }
  return blocks;
}

export default function BlogContent({ content, compact = false }: { content: string; compact?: boolean }) {
  return <div className={`${styles.content} ${compact ? styles.compact : ""}`}>
    {parseContent(content).map((block, index) => {
      if (block.type === "heading") {
        const Heading = `h${Math.max(2, block.level)}` as "h2" | "h3";
        return <Heading className={styles.heading} key={index}>{block.text}</Heading>;
      }
      if (block.type === "paragraph") return <p className={styles.paragraph} key={index}>{block.text}</p>;
      if (block.type === "ordered-list") {
        return <ol className={styles.orderedList} key={index} start={block.start}>
          {block.items.map((item, itemIndex) => <li key={itemIndex}>
            {item.split("\n").map((line, lineIndex, itemLines) => (
              <span key={lineIndex}>{line}{lineIndex < itemLines.length - 1 && <br />}</span>
            ))}
          </li>)}
        </ol>;
      }
      return <div className={styles.tableWrap} key={index}>
        <table className={styles.table}>
          <thead><tr>{block.headers.map((cell, cellIndex) => <th scope="col" key={cellIndex}>{cell}</th>)}</tr></thead>
          <tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>
            {block.headers.map((_, cellIndex) => <td key={cellIndex}>{row[cellIndex] ?? ""}</td>)}
          </tr>)}</tbody>
        </table>
      </div>;
    })}
  </div>;
}
