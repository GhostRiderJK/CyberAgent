/**
 * The only place a model class name is spelled, aliased or coloured.
 *
 * `MODEL_CLASSES` must equal the `labels` array of the evaluation artifact
 * (see scripts/build_evaluation_json.py); a Vitest test fails if the two drift.
 */
export const MODEL_CLASSES = [
  'BENIGN',
  'Bot',
  'DDoS',
  'DoS GoldenEye',
  'DoS Hulk',
  'DoS Slowhttptest',
  'DoS slowloris',
  'FTP-Patator',
  'PortScan',
  'SSH-Patator',
  'Web Attack',
] as const;

export type ModelClass = (typeof MODEL_CLASSES)[number];

/**
 * CIC-IDS2017 pcap-level attacks that appear in documentation and old fixtures but
 * are not outputs of the supervised flow classifier. Kept visible and labelled rather
 * than silently renamed, because hiding them would misrepresent what the model does.
 */
export const NOT_IN_MODEL_LABEL_SET = ['Heartbleed', 'Infiltration'] as const;

/** Spellings used elsewhere -> the model's own label. */
const CLASS_ALIASES: Record<string, ModelClass> = {
  'web attack': 'Web Attack',
  'webattack': 'Web Attack',
  'web attack - brute force': 'Web Attack',
  'web attack brute force': 'Web Attack',
  'web attack - brute force attack': 'Web Attack',
  'web attack xss': 'Web Attack',
  'web attack sql injection': 'Web Attack',
  'dos goldeneye': 'DoS GoldenEye',
  'dos golden eye': 'DoS GoldenEye',
  'dos slow http test': 'DoS Slowhttptest',
  'dos slowloris': 'DoS slowloris',
  'slowloris': 'DoS slowloris',
  'ftp patator': 'FTP-Patator',
  'ssh patator': 'SSH-Patator',
  'port scan': 'PortScan',
};

const MODEL_CLASS_LOOKUP = new Map(MODEL_CLASSES.map((c) => [c.toLowerCase(), c]));

/** Resolve aliases and casing to the model's label; returns the trimmed input otherwise. */
export function canonicalClass(name: string): string {
  const key = name.trim().toLowerCase();
  return MODEL_CLASS_LOOKUP.get(key) ?? CLASS_ALIASES[key] ?? name.trim();
}

export function isModelClass(name: string): boolean {
  return (MODEL_CLASSES as readonly string[]).includes(canonicalClass(name));
}

/** Label text safe to show anywhere: the canonical spelling when the model can emit it. */
export function displayClass(name: string): string {
  return canonicalClass(name);
}

/** Why a shown label is NOT something the trained model can output, when that applies. */
export const classLabelNote = (name: string): string | null =>
  isModelClass(name) ? null : 'not in model label set';

const CLASS_COLORS: Record<string, string> = {
  BENIGN: '#38bdf8',
  Bot: '#f87171',
  DDoS: '#fb923c',
  'DoS GoldenEye': '#facc15',
  'DoS Hulk': '#ef4444',
  'DoS Slowhttptest': '#a3e635',
  'DoS slowloris': '#4ade80',
  'FTP-Patator': '#22d3ee',
  PortScan: '#818cf8',
  'SSH-Patator': '#e879f9',
  'Web Attack': '#f472b6',
};

const FALLBACK_COLOR = '#94a3b8';

export function classColor(name: string): string {
  return CLASS_COLORS[canonicalClass(name)] ?? FALLBACK_COLOR;
}

/** Single flow-identifier format for every page (fixtures use numeric ids). */
export function flowIdLabel(id: number | string): string {
  const n = typeof id === 'number' ? id : Number(id);
  return Number.isFinite(n) ? `FLOW-${String(Math.trunc(n)).padStart(4, '0')}` : `FLOW-${id}`;
}
