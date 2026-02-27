import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/**
 * MSW server for jsdom-based Vitest tests.
 * Lifecycle is managed in src/test/setup.ts.
 */
export const server = setupServer(...handlers);
