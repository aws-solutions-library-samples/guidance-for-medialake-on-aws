import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "./locales/en";
import de from "./locales/de";
import pt from "./locales/pt";
import fr from "./locales/fr";
import zh from "./locales/zh";
import hi from "./locales/hi";
import ar from "./locales/ar";
import he from "./locales/he";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    debug: process.env.NODE_ENV === "development",
    fallbackLng: "en",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["navigator", "htmlTag", "path", "subdomain"],
      lookupFromPathIndex: 0,
      caches: ["localStorage"],
    },
    resources: {
      en: { translation: en },
      de: { translation: de },
      pt: { translation: pt },
      fr: { translation: fr },
      zh: { translation: zh },
      hi: { translation: hi },
      ar: { translation: ar },
      he: { translation: he },
    },
  });

export default i18n;
