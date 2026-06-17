import { useEffect, useState } from "react";

import type { PortalConfig, PortalDestination } from "@/features/portal/types/portal.types";

/**
 * Props passed by `survey-react-ui`'s {@link ReactQuestionFactory} to every
 * registered React question renderer. The factory invokes the registered
 * creator with `{ question, isDisplayMode, creator }` (see
 * `ReactQuestionFactory.createQuestionElement`), so a renderer reads its
 * question off `props.question`.
 *
 * `question` is typed loosely as {@link SurveyQuestionLike} rather than
 * `survey-core`'s `Question` so the renderers depend only on the small surface
 * they actually use (`survey`, `page`) and stay trivially testable with a plain
 * object stub.
 */
export interface PortalQuestionRendererProps {
  question: SurveyQuestionLike;
  /** SurveyJS read-only flag; the renderers prefer the explicit runtime mode. */
  isDisplayMode?: boolean;
  creator?: unknown;
}

/**
 * Minimal structural view of a SurveyJS `SurveyModel` used by the question
 * renderers. A real `SurveyModel` is structurally assignable to this shape, and
 * tests can pass a lightweight stub exposing the same members.
 */
export interface SurveyModelLike {
  /** Read a value from the flat `survey.data` answer object by key. */
  getValue(name: string): unknown;
  /** Write a value into the flat `survey.data` answer object by key. */
  setValue(name: string, newValue: unknown): void;
  /** Value-changed event; present on a real `SurveyModel`. */
  onValueChanged?: {
    add(cb: (sender: unknown, options: { name: string; value: unknown }) => void): void;
    remove(cb: (sender: unknown, options: { name: string; value: unknown }) => void): void;
  };
}

/**
 * Minimal structural view of a SurveyJS `Question` used by the renderers: its
 * owning survey and its page (whose `name` encodes the page number).
 */
export interface SurveyQuestionLike {
  survey?: SurveyModelLike | null;
  page?: { name?: string } | null;
}

/**
 * Parse the 1-based page number from a SurveyJS page name.
 *
 * {@link buildSurveyJson} names every page `page-{pageNumber}`, so the trailing
 * integer is the page the question lives on. Returns `null` when the name is
 * missing or does not match that shape (e.g. a legacy single-page survey),
 * letting callers fall back to non-page-scoped behavior.
 */
export function getQuestionPageNumber(question: SurveyQuestionLike): number | null {
  const name = question?.page?.name;
  if (typeof name !== "string") return null;
  const match = /^page-(\d+)$/.exec(name);
  if (!match) return null;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Return the destinations whose destination-selector appears on the given page.
 *
 * A destination targets a page via its `pageNumber`. To stay compatible with
 * portals saved before multi-page support (where no destination declares a
 * `pageNumber`), this falls back to offering ALL destinations when either no
 * destination declares a page number or the page number could not be derived.
 */
export function destinationsForPage(
  config: PortalConfig | null,
  pageNumber: number | null
): PortalDestination[] {
  const all = config?.destinations ?? [];
  if (all.length === 0) return [];
  const anyHasPageNumber = all.some((d) => typeof d.pageNumber === "number");
  if (!anyHasPageNumber || pageNumber === null) return all;
  return all.filter((d) => d.pageNumber === pageNumber);
}

/**
 * Read a reserved survey key reactively.
 *
 * Returns the current value of `survey.getValue(key)` and re-renders the
 * calling component whenever that key changes — including when ANOTHER question
 * (e.g. the destination selector on an earlier page) writes it. This is how the
 * path questions observe the chosen destination without prop drilling, since
 * SurveyJS instantiates question renderers itself.
 */
export function useSurveyValue<T = unknown>(
  survey: SurveyModelLike | null | undefined,
  key: string
): T | undefined {
  const [value, setValue] = useState<T | undefined>(() => survey?.getValue(key) as T | undefined);

  useEffect(() => {
    if (!survey) return;
    // Re-sync on mount/dependency change in case the value moved between the
    // initial render and this effect running.
    setValue(survey.getValue(key) as T | undefined);

    const event = survey.onValueChanged;
    if (!event) return;
    const handler = (_sender: unknown, options: { name: string }) => {
      if (options.name === key) {
        setValue(survey.getValue(key) as T | undefined);
      }
    };
    event.add(handler);
    return () => event.remove(handler);
  }, [survey, key]);

  return value;
}
