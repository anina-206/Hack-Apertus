import { useId, useMemo, useState } from "react";
import type { LanguageCode } from "../api";
import { LEHRBERUFE, type Lehrberuf } from "../data/lehrberufe";
import { occupationLabel, occupationName, qualification } from "../occupation";
import { ChevronDown } from "./icons";

type Props = {
  language: LanguageCode;
  value: Lehrberuf | null;
  onChange: (value: Lehrberuf) => void;
  placeholder: string;
  noResults: string;
  className?: string;
};

/** Lower case without accents, so "koechin" is not needed but "kochin" and "Köchin" both match. */
function normalize(s: string) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** The list for one language: sorted by the name in that language; the search also finds the German name. */
function listFor(language: LanguageCode) {
  return [...LEHRBERUFE]
    .map((o) => ({ o, name: occupationName(o, language), search: normalize(`${occupationLabel(o, language)} ${occupationLabel(o)}`) }))
    .sort((x, y) => x.name.localeCompare(y.name, language === "gsw" ? "de" : language) || x.o.abschluss.localeCompare(y.o.abschluss));
}

/** Searchable dropdown (combobox) with all Swiss apprenticeships from lehrberufe.ts. */
export default function OccupationPicker({ language, value, onChange, placeholder, noResults, className = "" }: Props) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  // Every word of the search has to appear somewhere in "Name EFZ"
  const sorted = useMemo(() => listFor(language), [language]);
  const results = useMemo(() => {
    const words = normalize(query).split(/\s+/).filter(Boolean);
    return sorted.filter((item) => words.every((w) => item.search.includes(w))).map((item) => item.o);
  }, [query, sorted]);

  function choose(o: Lehrberuf) {
    onChange(o);
    setOpen(false);
    setQuery("");
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && open && results[active]) {
      e.preventDefault();
      choose(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="relative">
      <input
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && results[active] ? `${listId}-${active}` : undefined}
        value={open ? query : value ? occupationLabel(value, language) : ""}
        placeholder={placeholder}
        onFocus={() => {
          setOpen(true);
          setQuery("");
          setActive(0);
        }}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
        autoComplete="off"
        className={`${className} pr-12`}
      />
      <ChevronDown className="pointer-events-none absolute top-1/2 right-5 h-5 w-5 -translate-y-1/2" />

      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-2 max-h-72 w-full overflow-y-auto rounded-2xl border-2 border-line bg-white py-1 shadow-card"
        >
          {results.length === 0 && <li className="px-5 py-3 text-charcoal-soft">{noResults}</li>}
          {results.map((o, i) => (
            <li
              key={occupationLabel(o)}  // the German label is unique in the list
              id={`${listId}-${i}`}
              role="option"
              aria-selected={value !== null && occupationLabel(value) === occupationLabel(o)}
              // mousedown (not click) so the input keeps focus until the choice is made
              onMouseDown={(e) => {
                e.preventDefault();
                choose(o);
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 px-5 py-2 text-base ${
                i === active ? "bg-brand-lighter" : ""
              }`}
            >
              <span>{occupationName(o, language)}</span>
              <span className="shrink-0 rounded-full bg-page px-2.5 py-0.5 text-xs font-bold text-charcoal-soft">
                {qualification(o, language)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
