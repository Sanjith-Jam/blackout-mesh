import { build } from 'esbuild';
import { mkdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
const directory = new URL('../node_modules/.cache/history-tests/', import.meta.url);
await mkdir(directory, { recursive: true });
const output = new URL('history-test.mjs', directory);
await build({ entryPoints: [new URL('../tests/history.test.tsx', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')],
  bundle: true, platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic',
  define: { 'import.meta.env': '{}' }, outfile: output.pathname.replace(/^\/(\w:)/, '$1') });
const result = spawnSync(process.execPath, ['--test', output.pathname.replace(/^\/(\w:)/, '$1')], { stdio: 'inherit' });
process.exitCode = result.status ?? 1;
