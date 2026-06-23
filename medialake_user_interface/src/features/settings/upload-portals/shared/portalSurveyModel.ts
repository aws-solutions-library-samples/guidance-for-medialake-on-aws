import type {
  PortalConfig,
  PortalMetadataField,
  PortalPage,
  PortalPageElement,
} from "@/features/portal/types/portal.types";

import { PORTAL_QUESTION_TYPES } from "./registerPortalQuestions";

/**
 * Minimal SurveyJS JSON shape produced by {@link buildSurveyJson}.
 *
 * `survey-core` does not export a public JSON-definition type, so we declare
 * the plain-object subset we emit. Keeping this a plain JSON shape (no class
 * instances, no functions) is what makes {@link buildSurveyJson} pure and its
 * output deep-equal-comparable across invocations.
 */
export interface ISurveyJsonQuestion {
  /** SurveyJS question type (built-in like `text`/`dropdown` or a custom portal type). */
  type: string;
  /** Unique question name; the key under which the answer lives in `survey.data`. */
  name: string;
  title?: string;
  isRequired?: boolean;
  /**
   * SurveyJS choices. Plain strings for admin-authored pick-lists, or
   * `{ value, text }` objects when the stored value differs from the display
   * label (used by the collection-picker role: value = collection id, text =
   * collection name).
   */
  choices?: Array<string | { value: string; text: string }>;
  /**
   * Tagbox free-entry: when true, the end user types a value and presses Enter
   * to add it as a tag — no predefined `choices` list is required. Emitted only
   * for the `tagbox` metadata type.
   */
  allowCustomChoices?: boolean;
  /** SurveyJS visibility expression, emitted character-for-character. */
  visibleIf?: string;
  /** SurveyJS enable expression, emitted character-for-character. */
  enableIf?: string;
}

export interface ISurveyJsonPage {
  /** Stable page name derived from the 1-based `pageNumber` (`page-{n}`). */
  name: string;
  title?: string;
  visibleIf?: string;
  enableIf?: string;
  elements: ISurveyJsonQuestion[];
}

export interface ISurveyJsonDefinition {
  pages: ISurveyJsonPage[];
}

/**
 * Fixed SurveyJS question names for the built-in (non metadata-field) elements.
 * Double-underscore prefixed so they never collide with metadata-field names
 * (which are slugified admin labels). These are constants — never generated —
 * which keeps the schema deterministic.
 */
const BUILTIN_QUESTION_NAMES = {
  destinationSelector: "__destPicker",
  pathBrowser: "__browser",
  pathBuilder: "__pathBuilder",
  uploader: "__uploader",
} as const;

/**
 * Default human-readable titles for the built-in (non metadata-field) questions.
 *
 * SurveyJS falls back to rendering a question's internal `name` when no `title`
 * is set, which would surface the reserved double-underscore names
 * (`__destPicker`, `__uploader`, …) in the portal UI. Emitting a friendly title
 * keeps those names internal while showing the admin/end-user a readable label.
 * These are sensible defaults; per-element authored titles override them.
 */
const BUILTIN_QUESTION_TITLES = {
  destinationSelector: "Destination",
  pathBrowser: "Upload location",
  pathBuilder: "Upload path",
  uploader: "Upload files",
} as const;

/**
 * Maps a {@link PortalMetadataField} `type` to its SurveyJS question `type`.
 *
 * - `select` → SurveyJS `dropdown` (single-select, choices from `options`).
 * - `radiogroup` → single-select radio buttons (choices from `options`).
 * - `checkbox` → multi-select checkboxes (choices from `options`; value is an array).
 * - `tagbox` → free-entry multi-value tags (type + Enter; value is an array of
 *   the entered strings — no predefined `options` list).
 * - `boolean` → yes/no toggle (value is a boolean).
 */
const METADATA_TYPE_TO_SURVEY_TYPE: Record<PortalMetadataField["type"], string> = {
  text: "text",
  number: "number",
  select: "dropdown",
  radiogroup: "radiogroup",
  checkbox: "checkbox",
  tagbox: "tagbox",
  boolean: "boolean",
};

/**
 * Metadata field types whose SurveyJS question derives its `choices` from the
 * field's admin-authored `options` array (a fixed pick-list). `tagbox` is
 * intentionally NOT here: it is a free-entry multi-value field (see
 * {@link buildMetadataQuestion}).
 */
const CHOICE_FIELD_TYPES: ReadonlySet<PortalMetadataField["type"]> = new Set([
  "select",
  "radiogroup",
  "checkbox",
]);

/**
 * Slugify an admin-authored label into a stable SurveyJS question name.
 *
 * Lower-cases, replaces every run of non-alphanumeric characters with a single
 * underscore, and trims leading/trailing underscores. e.g. `"Project code"` →
 * `"project_code"`, `"Region"` → `"region"`. Pure and deterministic: the same
 * label always yields the same slug.
 *
 * A `metadata-field` element references its field via `fieldKey`, which equals
 * `slug(label)` of the target {@link PortalMetadataField}; this is how the
 * element is matched back to its field definition.
 */
export function slug(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/**
 * Read any authored `visibleIf`/`enableIf` conditional expressions from a page
 * or element and return them verbatim (character-for-character). Only string
 * values are forwarded; everything else is dropped so the output stays a clean
 * JSON shape.
 */
function pickConditionalExpressions(source: { visibleIf?: string; enableIf?: string }): {
  visibleIf?: string;
  enableIf?: string;
} {
  const result: { visibleIf?: string; enableIf?: string } = {};
  if (typeof source.visibleIf === "string") result.visibleIf = source.visibleIf;
  if (typeof source.enableIf === "string") result.enableIf = source.enableIf;
  return result;
}

/**
 * Build the SurveyJS question for a `metadata-field` element from its resolved
 * {@link PortalMetadataField}. `name` is `slug(label)`, `title` is the raw
 * label, `isRequired` is emitted only when the field is required, and `select`
 * fields carry a copied `choices` array.
 */
function buildMetadataQuestion(field: PortalMetadataField): ISurveyJsonQuestion {
  // Collection-picker role: render as a single-select dropdown or multi-select
  // tagbox whose CHOICES are the admin-curated allowed collections
  // ({ value: id, text: name }). The field's own `type` is ignored for layout
  // purposes here — the role dictates the control. The server re-validates the
  // chosen ids against the saved allow-list at upload time.
  if (field.role === "collection-picker") {
    const allowed = field.roleConfig?.allowedCollections ?? [];
    const multiple = field.roleConfig?.multiple ?? true;
    const question: ISurveyJsonQuestion = {
      type: multiple ? "tagbox" : "dropdown",
      name: slug(field.label),
      title: field.label,
      choices: allowed.map((c) => ({ value: c.id, text: c.name })),
    };
    if (field.required) question.isRequired = true;
    return question;
  }

  const question: ISurveyJsonQuestion = {
    type: METADATA_TYPE_TO_SURVEY_TYPE[field.type],
    name: slug(field.label),
    title: field.label,
  };
  if (field.required) question.isRequired = true;
  if (CHOICE_FIELD_TYPES.has(field.type) && Array.isArray(field.options)) {
    // Copy so the output never shares a reference with the input config.
    question.choices = [...field.options];
  }
  if (field.type === "tagbox") {
    // Free-entry tags: the end user types a value and presses Enter to add it.
    // Any admin-authored `options` become suggested choices but are not
    // required; with none the field starts empty and accepts arbitrary tags.
    question.allowCustomChoices = true;
    if (Array.isArray(field.options) && field.options.length > 0) {
      question.choices = [...field.options];
    }
  }
  return question;
}

/**
 * Map a single {@link PortalPageElement} to its SurveyJS question.
 *
 * `metadata-field` elements are resolved against `metadataFields` by matching
 * `slug(field.label) === element.fieldKey`; an element with no matching field
 * yields `null` and is omitted from the page. Built-in element kinds map to the
 * custom portal question types. Any authored `visibleIf`/`enableIf` on the
 * element is passed straight through and overrides builder defaults (e.g. the
 * `path-browser` default visibility expression).
 */
function buildQuestion(
  element: PortalPageElement,
  metadataFields: PortalMetadataField[],
  pageDestinationCount: number
): ISurveyJsonQuestion | null {
  const authored = pickConditionalExpressions(element as { visibleIf?: string; enableIf?: string });
  // Allow a per-element authored title to override the built-in default
  // (forward-compatible: the element union has no `title` today, but an admin
  // editor may add one later). Only a non-empty string overrides.
  const authoredTitle = (element as { title?: unknown }).title;
  const titleOverride =
    typeof authoredTitle === "string" && authoredTitle.trim().length > 0
      ? { title: authoredTitle }
      : {};

  switch (element.kind) {
    case "metadata-field": {
      const field = metadataFields.find((f) => slug(f.label) === element.fieldKey);
      if (!field) return null;
      return { ...buildMetadataQuestion(field), ...authored };
    }
    case "destination-selector":
      // A destination selector is only useful when the page offers MORE THAN
      // ONE destination to choose between. With zero or one destination the
      // uploader auto-resolves the sole/implicit destination at runtime
      // (see UppyUploaderQuestion + DestinationSelectorRenderer's auto-select),
      // so emitting the question here would just render an empty "Destination"
      // card with nothing to pick. Omit it entirely in that case.
      if (pageDestinationCount <= 1) return null;
      return {
        type: PORTAL_QUESTION_TYPES.destinationSelector,
        name: BUILTIN_QUESTION_NAMES.destinationSelector,
        title: BUILTIN_QUESTION_TITLES.destinationSelector,
        ...titleOverride,
        ...authored,
      };
    case "path-browser":
      return {
        type: PORTAL_QUESTION_TYPES.pathBrowser,
        name: BUILTIN_QUESTION_NAMES.pathBrowser,
        title: BUILTIN_QUESTION_TITLES.pathBrowser,
        ...titleOverride,
        // Only meaningful once a destination has been chosen on an earlier page.
        visibleIf: "{__selectedDestinationId} notempty",
        ...authored,
      };
    case "path-builder":
      return {
        type: PORTAL_QUESTION_TYPES.pathBuilder,
        name: BUILTIN_QUESTION_NAMES.pathBuilder,
        title: BUILTIN_QUESTION_TITLES.pathBuilder,
        ...titleOverride,
        ...authored,
      };
    case "uploader":
      return {
        type: PORTAL_QUESTION_TYPES.uploader,
        name: BUILTIN_QUESTION_NAMES.uploader,
        title: BUILTIN_QUESTION_TITLES.uploader,
        ...titleOverride,
        isRequired: true,
        ...authored,
      };
    default: {
      // Exhaustiveness guard: a new element kind must be handled explicitly.
      const _exhaustive: never = element;
      return _exhaustive;
    }
  }
}

/** Map one {@link PortalPage} to a SurveyJS page, preserving element order. */
function buildPage(
  page: PortalPage,
  metadataFields: PortalMetadataField[],
  pageDestinationCount: number
): ISurveyJsonPage {
  const elements = (page.elements ?? [])
    .map((element) => buildQuestion(element, metadataFields, pageDestinationCount))
    .filter((question): question is ISurveyJsonQuestion => question !== null);

  return {
    name: `page-${page.pageNumber}`,
    title: page.title,
    ...pickConditionalExpressions(page),
    elements,
  };
}

/**
 * Build a SurveyJS JSON definition from a portal {@link PortalConfig}.
 *
 * This function is the single, shared source of truth for the form schema: both
 * the admin live preview and the public renderer derive their schema from it, so
 * they stay in lockstep.
 *
 * Mapping rules:
 *   - {@link PortalPage} → SurveyJS page `{ name: "page-{pageNumber}", title, visibleIf }`
 *   - `metadata-field` element → `{ type: text|email|number|dropdown, name: slug(label),
 *     title, isRequired?, choices? }`
 *   - `destination-selector` → `{ type: "portal-destination-selector", name }`
 *   - `path-browser` → `{ type: "portal-path-browser", name,
 *     visibleIf: "{__selectedDestinationId} notempty" }`
 *   - `path-builder` → `{ type: "portal-path-builder", name }`
 *   - `uploader` → `{ type: "portal-uppy-uploader", name: "__uploader", isRequired: true }`
 *
 * Any authored `visibleIf`/`enableIf` on a page or element is emitted
 * character-for-character.
 *
 * Purity (Property 8 / Requirement 6.3): the result is a function of `config`
 * alone. There is no dependency on external or mutable state, no clock or random
 * source, and ordering is deterministic — pages are sorted by ascending
 * `pageNumber` and each page's `elements` order is preserved exactly. The input
 * config is never mutated. Therefore the same input always produces a deep-equal
 * output.
 */
export function buildSurveyJson(config: PortalConfig): ISurveyJsonDefinition {
  const metadataFields = config.metadataFields ?? [];
  const destinations = config.destinations ?? [];
  // Mirror `destinationsForPage` (questionHelpers): destinations target a page
  // via `pageNumber`, but portals saved before multi-page support declare none,
  // in which case ALL destinations are offered on every page.
  const anyDestinationHasPageNumber = destinations.some((d) => typeof d.pageNumber === "number");
  const countDestinationsForPage = (pageNumber: number): number =>
    anyDestinationHasPageNumber
      ? destinations.filter((d) => d.pageNumber === pageNumber).length
      : destinations.length;

  const pages = [...(config.pages ?? [])]
    // Sort a copy so the caller's array is never mutated. Ascending pageNumber.
    .sort((a, b) => a.pageNumber - b.pageNumber)
    .map((page) => buildPage(page, metadataFields, countDestinationsForPage(page.pageNumber)));

  return { pages };
}
