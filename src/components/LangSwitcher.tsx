import clsx from "clsx";
import type { UILang } from "@/i18n/translations";

const LANGS: { code: UILang; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "es", label: "ES" },
  { code: "am", label: "አማ" },
];

interface Props {
  current: string;
  onChange: (lang: UILang) => void;
}

export function LangSwitcher({ current, onChange }: Props) {
  return (
    <div className="flex gap-0.5 text-[11px] font-medium" role="radiogroup" aria-label="Language">
      {LANGS.map((l) => (
        <button
          key={l.code}
          type="button"
          onClick={() => onChange(l.code)}
          role="radio"
          aria-checked={current === l.code}
          className={clsx(
            "px-2 py-1.5 rounded-lg transition-colors min-h-[32px]",
            current === l.code
              ? "bg-sage/10 text-sage-deep font-semibold"
              : "text-ink-muted hover:text-ink hover:bg-white/30",
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
