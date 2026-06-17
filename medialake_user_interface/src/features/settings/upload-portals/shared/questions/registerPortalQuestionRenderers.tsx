import React from "react";
import { ReactQuestionFactory } from "survey-react-ui";

import { PORTAL_QUESTION_TYPES, registerPortalQuestions } from "../registerPortalQuestions";
import DestinationSelectorRenderer from "./DestinationSelectorQuestion";
import PathBrowserRenderer from "./PathBrowserQuestion";
import PathBuilderRenderer from "./PathBuilderQuestion";
import type { PortalQuestionRendererProps } from "./questionHelpers";
// Task 11.3 — self-contained, idempotent registration of the Uppy uploader
// renderer (model + ReactQuestionFactory binding) lives in its own module.
import { registerUppyUploaderRenderer } from "./UppyUploaderQuestion";

/**
 * Binds the React renderers for the custom portal SurveyJS questions.
 *
 * The MODELS (each extending `survey-core`'s `Question`) are registered by
 * {@link registerPortalQuestions} in `../registerPortalQuestions.ts`; that
 * module is intentionally React-free so the pure schema/model layer can be
 * imported without pulling in React or MUI. THIS module is the React-aware
 * companion that binds each model's renderer via `survey-react-ui`'s
 * {@link ReactQuestionFactory}.
 *
 * `ReactQuestionFactory` invokes the registered creator with the props object
 * `{ question, isDisplayMode, creator }` (see
 * `ReactQuestionFactory.createQuestionElement`), so each creator forwards those
 * props straight into the renderer component.
 *
 * Renderers owned by THIS task (11.2): destination-selector, path-browser,
 * path-builder. The Uppy uploader renderer is added by task 11.3 — see the
 * extension point below.
 */

/**
 * Module-level guard so repeated calls (HMR, both render paths importing this
 * module) are no-ops. `registerQuestion` itself overwrites silently, but the
 * guard plus the per-type check below avoid redundant work and keep behaviour
 * symmetric with {@link registerPortalQuestions}.
 */
let renderersRegistered = false;

/** Register one renderer creator unless its type is already bound. */
function registerRenderer(
  type: string,
  Renderer: React.ComponentType<PortalQuestionRendererProps>
): void {
  if (ReactQuestionFactory.Instance.getAllTypes().indexOf(type) !== -1) return;
  ReactQuestionFactory.Instance.registerQuestion(type, (props) =>
    // `registerQuestion` types the creator arg as `string`, so cast through
    // unknown to the actual `{ question, isDisplayMode, creator }` props shape.
    React.createElement(Renderer, props as unknown as PortalQuestionRendererProps)
  );
}

/**
 * Register the React renderers for the portal custom questions exactly once.
 *
 * Ensures the MODELS are registered first (so a schema referencing the custom
 * types parses), then binds each renderer. Idempotent across repeated calls and
 * HMR.
 *
 * @see registerPortalQuestions (the React-free model registration)
 */
export function registerPortalQuestionRenderers(): void {
  if (renderersRegistered) return;

  // Models must exist before their renderers are meaningful; this call is
  // itself idempotent.
  registerPortalQuestions();

  registerRenderer(PORTAL_QUESTION_TYPES.destinationSelector, DestinationSelectorRenderer);
  registerRenderer(PORTAL_QUESTION_TYPES.pathBrowser, PathBrowserRenderer);
  registerRenderer(PORTAL_QUESTION_TYPES.pathBuilder, PathBuilderRenderer);

  // --- Extension point (task 11.3) -------------------------------------
  // The Uppy uploader renderer (PORTAL_QUESTION_TYPES.uploader) is owned by
  // task 11.3 in `./UppyUploaderQuestion.tsx`, which self-registers at module
  // init and exposes an idempotent registrar. Calling it here makes this
  // aggregator the single init point for all four renderers; its own guard +
  // the factory per-type check keep it a no-op on repeat calls.
  registerUppyUploaderRenderer();
  // ---------------------------------------------------------------------

  renderersRegistered = true;
}

// Register at module init so the renderers are bound as soon as this module is
// imported by a render path. The guard above makes this safe alongside explicit
// caller invocations and HMR.
registerPortalQuestionRenderers();
