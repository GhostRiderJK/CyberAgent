#!/usr/bin/env node
/**
 * Copy the single evaluation artifact into the frontend bundle.
 *
 *   npm run sync:eval
 *
 * Source : ../artifacts/eval/evaluation.json  (built by scripts/build_evaluation_json.py)
 * Target : src/data/evaluation.json           (the only metrics file the UI reads)
 *
 * When the artifact is absent this writes an explicit "unavailable" record instead of
 * sample numbers, so the page can show the regeneration command rather than inventing
 * anything. A present-but-malformed artifact is a bug and fails the command.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, '..');
const SOURCE = resolve(FRONTEND, '../artifacts/eval/evaluation.json');
const TARGET = resolve(FRONTEND, 'src/data/evaluation.json');

const REBUILD = 'python scripts/build_evaluation_json.py   (or: make eval-json)';

const REQUIRED = [
  'schema_version', 'generated_at', 'labels', 'models', 'best_model',
  'selection_rule', 'confusion_matrix', 'per_class', 'pr_curves', 'dataset',
];

function fail(message) {
  console.error(`[sync:eval] ${message}`);
  process.exit(1);
}

let raw;
try {
  raw = JSON.parse(readFileSync(SOURCE, 'utf8'));
} catch (err) {
  if (err.code === 'ENOENT') {
    const doc = {
      available: false,
      reason: `No evaluation artifact at ${SOURCE}.`,
      command: REBUILD,
      requires: 'models/metrics.json (make train) and results/tables/evaluation_summary.json (make evaluate)',
    };
    mkdirSync(dirname(TARGET), { recursive: true });
    writeFileSync(TARGET, `${JSON.stringify(doc, null, 2)}\n`, 'utf8');
    console.warn(
      `[sync:eval] evaluation artifact missing - wrote an "unavailable" placeholder.\n` +
      `[sync:eval] Model Results will show the empty state until you run: ${REBUILD}`,
    );
    process.exit(0);
  }
  fail(`could not parse ${SOURCE}: ${err.message}`);
}

const missing = REQUIRED.filter((k) => raw[k] === undefined || raw[k] === null);
if (missing.length) fail(`artifact is missing required field(s): ${missing.join(', ')}`);
if (!Array.isArray(raw.labels) || !raw.labels.length) fail('artifact has no labels');
const matrix = raw.confusion_matrix?.matrix;
if (!Array.isArray(matrix) || matrix.length !== raw.labels.length) {
  fail('confusion_matrix.matrix is not square over the label list');
}
if (matrix.some((row) => row.length !== raw.labels.length)) {
  fail('confusion_matrix.matrix has a row whose length differs from the label count');
}
if (!raw.models[raw.best_model]) fail(`best_model "${raw.best_model}" is not in models`);
if (raw.pr_curves?.model !== raw.best_model) {
  fail('pr_curves.model must be the best model; regenerate the artifact');
}

const out = { available: true, source_path: 'artifacts/eval/evaluation.json', ...raw };
mkdirSync(dirname(TARGET), { recursive: true });
writeFileSync(TARGET, `${JSON.stringify(out, null, 2)}\n`, 'utf8');
console.log(
  `[sync:eval] ${TARGET}\n` +
  `[sync:eval] ${Object.keys(raw.models).length} models, ${raw.labels.length} classes, ` +
  `${raw.dataset.n_samples} test samples, best=${raw.best_model}, generated ${raw.generated_at}`,
);
