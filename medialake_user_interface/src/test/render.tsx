import { render, type RenderOptions } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactElement } from "react";

/**
 * Custom render that sets up userEvent and returns both.
 * Extend this with providers (QueryClient, Router, Theme) as needed.
 */
export function renderWithUser(ui: ReactElement, options?: RenderOptions) {
  const user = userEvent.setup();
  return { user, ...render(ui, options) };
}

export { render } from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";
