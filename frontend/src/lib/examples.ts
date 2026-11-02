import { searchTags, type TagSearchHit } from "@/lib/api";

type Search = (q: string) => Promise<TagSearchHit[]>;

/** Beispielfragen aus Kennzeichen, die im Index stehen; was die Suche nicht findet, wird nicht vorgeschlagen. */
export async function exampleQuestions(search: Search = searchTags): Promise<string[]> {
  const firstOf = async (query: string, type: string) =>
    (await search(query).catch(() => [])).find((hit) => hit.tag_type === type)?.tag;
  // Der groesste Baustein erklaert am meisten; die Suche liefert Bausteine nach Name, "FB 1" vor "FB \"Motor\""
  const biggestBlock = async () =>
    (await search("FB").catch(() => []))
      .filter((hit) => hit.tag_type === "plc_block")
      .sort((a, b) => b.occurrences - a.occurrences)[0]?.tag;
  const [contactor, terminal, block, motor] = await Promise.all([
    firstOf("-K", "device"),
    firstOf("-X", "terminal"),
    biggestBlock(),
    firstOf("-M", "device"),
  ]);
  return [
    contactor && `Wo ist ${contactor} verbaut und was schaltet es?`,
    terminal && `Wohin führt Klemme ${terminal} und was hängt daran?`,
    block && `Erkläre mir ${block} Netzwerk für Netzwerk.`,
    motor && `Motor ${motor} läuft nicht an: welche Bedingungen müssen erfüllt sein?`,
  ].filter((question): question is string => Boolean(question));
}
