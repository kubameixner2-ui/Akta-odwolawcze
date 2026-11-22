import { loadPyodide } from './vendor/pyodide/pyodide.mjs';

let parser;

async function loadRules() {
  const runtime = await loadPyodide({ indexURL: new URL('./vendor/pyodide/', import.meta.url).href });
  runtime.FS.mkdir('config');
  const files = ['fields.py', 'browser_rules.py', 'config/causes.json', 'config/odwolanie.json',
    'config/pelnomocnictwo.json', 'config/przelew.json'];
  await Promise.all(files.map(async path => {
    const response = await fetch(new URL(path, import.meta.url));
    if (!response.ok) throw new Error(`Nie udało się pobrać pliku ${path} (HTTP ${response.status}).`);
    runtime.FS.writeFile(path, await response.text());
  }));
  return runtime.runPython('from browser_rules import extract_json\nextract_json');
}

export async function extractFields(pages) {
  parser ??= loadRules().catch(error => { parser = undefined; throw error; });
  return JSON.parse((await parser)(JSON.stringify(pages)));
}
