import { aiUseEntries, aiUseSummary } from '@/lib/ai-use';

export default function AiUsePage() {
  const entries = aiUseEntries();
  return (
    <div className="page-frame max-w-3xl">
      <div className="eyebrow">How AI is used</div>
      <h1 className="display-title text-4xl mt-3">Plain words for each step.</h1>
      <p className="body-muted mt-4 leading-relaxed" data-testid="text-ai-use-summary">
        {aiUseSummary()}
      </p>
      <div className="mt-8 flex flex-col gap-3">
        {entries.map((entry) => (
          <details key={entry.id} className="panel panel-padded" data-testid={`ai-use-${entry.id}`}>
            <summary className="font-semibold cursor-pointer">{entry.whatItIs}</summary>
            <p className="text-sm leading-relaxed mt-3"><span className="font-semibold">What it does. </span>{entry.whatItDoes}</p>
            <p className="text-sm leading-relaxed mt-2"><span className="font-semibold">What it doesn't do. </span>{entry.whatItDoesnt}</p>
            <p className="body-muted text-xs mt-3">Code: {entry.codePath}</p>
          </details>
        ))}
      </div>
    </div>
  );
}
