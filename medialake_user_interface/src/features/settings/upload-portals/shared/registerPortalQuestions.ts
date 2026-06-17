import { ElementFactory, Question, Serializer } from "survey-core";

/**
 * Question type name constants — the string written into the SurveyJS JSON
 * schema `type` field by {@link buildSurveyJson} and matched by the registered
 * question models / React renderers.
 *
 * These names are the single source of truth shared between the schema builder
 * ({@link ./portalSurveyModel.ts}) and the registry below, so the values MUST
 * stay in sync with the design's "Custom SurveyJS question contracts" section.
 */
export const PORTAL_QUESTION_TYPES = {
  destinationSelector: "portal-destination-selector",
  pathBrowser: "portal-path-browser",
  pathBuilder: "portal-path-builder",
  uploader: "portal-uppy-uploader",
} as const;

/**
 * Custom question MODELS. Each extends `survey-core`'s {@link Question} and
 * returns its own type name from {@link Question.getType}, so the four custom
 * types exist in the SurveyJS Core registry and a schema referencing them can
 * be parsed without falling back to the unknown-question placeholder.
 *
 * These are intentionally thin — the React renderers and the full model
 * behavior (reading/writing the reserved survey keys, wrapping the existing
 * uploader/selector/browser/builder components) are wired up in a later task
 * via `ReactQuestionFactory`. This module only owns the model registration and
 * the idempotency guard.
 */
class QuestionDestinationSelectorModel extends Question {
  public getType(): string {
    return PORTAL_QUESTION_TYPES.destinationSelector;
  }
}

class QuestionPathBrowserModel extends Question {
  public getType(): string {
    return PORTAL_QUESTION_TYPES.pathBrowser;
  }
}

class QuestionPathBuilderModel extends Question {
  public getType(): string {
    return PORTAL_QUESTION_TYPES.pathBuilder;
  }
}

class QuestionUppyUploaderModel extends Question {
  public getType(): string {
    return PORTAL_QUESTION_TYPES.uploader;
  }
}

/**
 * Maps each custom type name to the factory that constructs its model. The
 * factory signature `(name: string) => Question` is what both
 * {@link Serializer.addClass} and {@link ElementFactory.registerElement}
 * expect.
 */
const QUESTION_MODEL_FACTORIES: ReadonlyArray<{
  type: string;
  create: (name: string) => Question;
}> = [
  {
    type: PORTAL_QUESTION_TYPES.destinationSelector,
    create: (name) => new QuestionDestinationSelectorModel(name),
  },
  {
    type: PORTAL_QUESTION_TYPES.pathBrowser,
    create: (name) => new QuestionPathBrowserModel(name),
  },
  {
    type: PORTAL_QUESTION_TYPES.pathBuilder,
    create: (name) => new QuestionPathBuilderModel(name),
  },
  {
    type: PORTAL_QUESTION_TYPES.uploader,
    create: (name) => new QuestionUppyUploaderModel(name),
  },
];

/**
 * Module-level guard. Set on the first successful {@link registerPortalQuestions}
 * call so subsequent in-session calls (e.g. both render paths importing this
 * module) short-circuit to a no-op.
 */
let registered = false;

/**
 * Register a single custom question type with SurveyJS Core, but only when it
 * is not already present. Guarding each type against the live registries makes
 * the registration safe across hot-module-replacement: HMR resets the
 * module-level {@link registered} flag while the global SurveyJS registries
 * persist, so re-running registration would otherwise throw or duplicate.
 *
 * After any number of calls, exactly one registration per type remains.
 */
function registerQuestionType(type: string, create: (name: string) => Question): void {
  // Serializer.addClass throws if the class already exists; skip when present.
  if (!Serializer.findClass(type)) {
    Serializer.addClass(type, [], () => create(""), "question");
  }
  // ElementFactory silently overwrites, but skip to avoid redundant work and
  // keep behavior symmetric with the Serializer guard.
  if (ElementFactory.Instance.getAllTypes().indexOf(type) === -1) {
    ElementFactory.Instance.registerElement(type, (name) => create(name));
  }
}

/**
 * Register the four custom portal question MODELS with SurveyJS Core exactly
 * once.
 *
 * Idempotent (Requirements 7.2, 15.4): a module-level boolean short-circuits
 * repeated calls within a session, and each individual registration is also
 * guarded against the live SurveyJS registries so repeated calls — including
 * after HMR — are no-ops that never throw and leave exactly one registration
 * per question type in place.
 *
 * Intended to run once at module initialization (see the call at the bottom of
 * this file) so every custom type exists before either render path builds a
 * schema; it is also exported so callers can invoke it explicitly, and the
 * guard makes doing both safe.
 */
export function registerPortalQuestions(): void {
  if (registered) return;
  for (const { type, create } of QUESTION_MODEL_FACTORIES) {
    registerQuestionType(type, create);
  }
  registered = true;
}

// Register at module init so the custom types exist before any survey schema is
// built. The guard above makes this safe alongside explicit caller invocations.
registerPortalQuestions();
