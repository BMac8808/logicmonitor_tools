import { useLibrary } from "../ui";

export default function ContextChips({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const { contextTags } = useLibrary();
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  return (
    <div className="chips" role="group" aria-label="Technical context">
      {contextTags.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`chip${value.includes(t.id) ? " selected" : ""}`}
          aria-pressed={value.includes(t.id)}
          onClick={() => toggle(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
