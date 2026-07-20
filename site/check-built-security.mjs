import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("./dist/", import.meta.url));

async function findHtmlFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await findHtmlFiles(path)));
    } else if (entry.isFile() && entry.name.endsWith(".html")) {
      files.push(path);
    }
  }

  return files;
}

const htmlFiles = await findHtmlFiles(root);
const failures = [];

for (const file of htmlFiles) {
  const html = await readFile(file, "utf8");
  const label = relative(root, file);

  if (!html.includes('http-equiv="Content-Security-Policy"')) {
    failures.push(`${label}: content policy is missing`);
  }
  if (html.includes("'unsafe-inline'")) {
    failures.push(`${label}: unsafe inline content is permitted`);
  }
  if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(html)) {
    failures.push(`${label}: inline script detected`);
  }
  if (/<style(?:\s|>)/i.test(html) || /\sstyle\s*=/i.test(html)) {
    failures.push(`${label}: inline style detected`);
  }
  if (/\son[a-z]+\s*=/i.test(html)) {
    failures.push(`${label}: inline event handler detected`);
  }
  if (/(?:href|src)\s*=\s*["']\s*javascript:/i.test(html)) {
    failures.push(`${label}: JavaScript URL detected`);
  }
}

if (htmlFiles.length === 0) {
  failures.push("no generated HTML files were found");
}

if (failures.length > 0) {
  throw new Error(`Built-site security checks failed:\n${failures.join("\n")}`);
}

console.log(`Verified ${htmlFiles.length} HTML files without prohibited inline browser content.`);
