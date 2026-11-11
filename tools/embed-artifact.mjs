/**
 * embed-artifact.mjs — gera uma cópia self-contained do app (fontes + orbs embutidos como data URIs)
 * para publicar como preview/artifact. Lê mobile/www/index.html e escreve o HTML inlined.
 *
 * Uso: node tools/embed-artifact.mjs [saida.html]
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const wwwDir = resolve(root, 'mobile/www');
const out = process.argv[2] || resolve(root, 'dist/pulse-loop-app.html');

let html = readFileSync(resolve(wwwDir, 'index.html'), 'utf8');

const b64 = (p) => readFileSync(resolve(wwwDir, p)).toString('base64');

// 1) fontes: url('assets/fonts/X.woff2') -> data URI
html = html.replace(/url\('assets\/fonts\/([^']+\.woff2)'\)/g,
  (_, f) => `url(data:font/woff2;base64,${b64('assets/fonts/' + f)})`);

// 2) orbs + mark: '<name>.png' -> 'data:image/png;base64,...'
html = html.replace(/'((?:orb-[a-z]+|mark)\.png)'/g,
  (_, f) => `'data:image/png;base64,${b64('assets/' + f)}'`);

// 3) scripts locais (engine.js, health-connect.js) -> inline (self-contained p/ preview)
html = html.replace(/<script src="([^"]+\.js)"><\/script>/g,
  (_, f) => `<script>/* ${f} */\n${readFileSync(resolve(wwwDir, f), 'utf8')}</script>`);

writeFileSync(out, html);
console.log('Artifact self-contained gerado:', out, `(${(html.length / 1024).toFixed(0)} KB)`);
