// BUG-19 fix: every locale registered in ``src/i18n/i18n.ts`` MUST appear here,
// or the Profile language selector renders a subset that ships translation
// weight but is unreachable. Adding a locale is now a one-line change instead
// of a duplicated 55-line MenuItem block. Keep in sync with ``i18n/i18n.ts``.
export type ProfileLocale = {
  code: string;
  flag: string; // 2-letter country code shown as a text-only "flag" placeholder
  translationKey: string; // key under ``languages`` in each locale bundle
};

export const PROFILE_LOCALES: ReadonlyArray<ProfileLocale> = [
  { code: "en", flag: "GB", translationKey: "languages.english" },
  { code: "de", flag: "DE", translationKey: "languages.german" },
  { code: "es", flag: "ES", translationKey: "languages.spanish" },
  { code: "pt", flag: "PT", translationKey: "languages.portuguese" },
  { code: "fr", flag: "FR", translationKey: "languages.french" },
  { code: "ja", flag: "JP", translationKey: "languages.japanese" },
  { code: "ko", flag: "KR", translationKey: "languages.korean" },
  { code: "zh", flag: "CN", translationKey: "languages.chinese" },
  { code: "hi", flag: "IN", translationKey: "languages.hindi" },
  { code: "ar", flag: "SA", translationKey: "languages.arabic" },
  { code: "he", flag: "IL", translationKey: "languages.hebrew" },
];

/**
 * The selector option for the active language. i18next reports the detected
 * browser language as-is ("en-US", "pt-BR"), which matches no option and left
 * the selector blank, so fall back to its base language, then to English.
 */
export function selectedProfileLocale(
  language: string | undefined,
  resolvedLanguage?: string
): string {
  const known = (code?: string) => !!code && PROFILE_LOCALES.some((locale) => locale.code === code);
  const base = language?.split("-")[0];
  if (known(language)) return language as string;
  if (known(resolvedLanguage)) return resolvedLanguage as string;
  if (known(base)) return base as string;
  return "en";
}
