import { readdir, readFile } from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";
import { parseComplianceCard, searchComplianceCards, type ComplianceCard } from "./cards";

let cardsPromise: Promise<ComplianceCard[]> | undefined;

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map((entry) => {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) return markdownFiles(path);
      return entry.isFile() && entry.name.endsWith(".md") ? [path] : [];
    }),
  );
  return nested.flat().sort();
}

async function readCards() {
  const projectRoot = process.env.PRECOG_PROJECT_ROOT ?? process.cwd();
  const cardRoot = resolve(projectRoot, "knowledge", "compliance");
  const files = await markdownFiles(cardRoot);
  return Promise.all(
    files.map(async (path) => {
      const section = relative(cardRoot, dirname(path)).split(sep)[0];
      return parseComplianceCard(await readFile(path, "utf8"), section);
    }),
  );
}

async function loadCards() {
  const pending = cardsPromise ?? (cardsPromise = readCards());
  try {
    return await pending;
  } catch (error) {
    if (cardsPromise === pending) cardsPromise = undefined;
    throw error;
  }
}

export async function searchComplianceCardsFromDisk(query: string, section?: string) {
  return searchComplianceCards(query, await loadCards(), { section });
}
