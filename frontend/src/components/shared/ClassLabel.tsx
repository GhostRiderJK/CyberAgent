import { classLabelNote, classColor, displayClass } from '@/lib/classLabels';

interface Props {
  name: string;
  withDot?: boolean;
}

/**
 * Class name rendered from the single label source. A label the trained model cannot
 * output stays visible but is marked, instead of being quietly renamed to something it
 * can output.
 */
export default function ClassLabel({ name, withDot = false }: Props) {
  const note = classLabelNote(name);
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      {withDot && (
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: classColor(name) }}
          aria-hidden="true"
        />
      )}
      <span style={{ color: classColor(name) }}>{displayClass(name)}</span>
      {note && (
        <span className="rounded bg-amber-400/15 px-1 py-0.5 text-[10px] text-amber-200" title={`The classifier was not trained on ${name}.`}>
          {note}
        </span>
      )}
    </span>
  );
}
