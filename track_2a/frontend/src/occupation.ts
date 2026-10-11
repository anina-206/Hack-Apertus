import type { LanguageCode } from "./api";
import type { Lehrberuf } from "./data/lehrberufe";
import { LEHRBERUF_NAMEN } from "./data/lehrberufe.i18n";

type UiLanguage = "de" | "fr" | "it";

/** Swiss German (gsw) uses the German names. */
function uiLanguage(lang: LanguageCode): UiLanguage {
  return lang === "fr" || lang === "it" ? lang : "de";
}

/** The qualification in the language: EFZ/EBA (de), CFC/AFP (fr), AFC/CFP (it). */
export function qualification(o: Lehrberuf, lang: LanguageCode): string {
  const lookup = { de: { EFZ: "EFZ", EBA: "EBA" }, fr: { EFZ: "CFC", EBA: "AFP" }, it: { EFZ: "AFC", EBA: "CFP" } };
  return lookup[uiLanguage(lang)][o.abschluss];
}

/** The name without the qualification, in the language (the German name if there is no translation). */
export function occupationName(o: Lehrberuf, lang: LanguageCode): string {
  const ui = uiLanguage(lang);
  return ui === "de" ? o.name : (LEHRBERUF_NAMEN[`${o.name}|${o.abschluss}`]?.[ui] ?? o.name);
}

/** "Koch/Köchin EFZ", "Cuisinier/ère CFC", "Cuoco/a AFC". Default language: German (the names the backend knows). */
export function occupationLabel(o: Lehrberuf, lang: LanguageCode = "de"): string {
  return `${occupationName(o, lang)} ${qualification(o, lang)}`;
}
