# MediaLake User Interface

Web-based interface for the MediaLake platform — manage media assets, collections, pipelines, and workflows.

Built with React 19, TypeScript, MUI 7, and Vite 7. Authenticates via AWS Cognito and communicates with the MediaLake API through CloudFront.

## Prerequisites

- Node.js v18+
- npm
- AWS account with Cognito user pool configured
- `public/aws-exports.json` with your environment's Auth + API config (deployed automatically by the backend stack)

## Quick Start

```bash
npm install
npm run dev            # http://localhost:5173
```

Copy `.env.example` → `.env` if you need pipeline API keys (TwelveLabs, Coactive).

## Scripts

| Command                    | Description                         |
| -------------------------- | ----------------------------------- |
| `npm run dev`              | Vite dev server (HMR)               |
| `npm run build`            | TypeScript check + production build |
| `npm run preview`          | Preview production build locally    |
| `npm run format`           | Prettier format `src/`              |
| `npm run test`             | Vitest unit tests (single run)      |
| `npm run test:watch`       | Vitest in watch mode                |
| `npm run test:ui`          | Vitest browser UI                   |
| `npm run test:coverage`    | Vitest with v8 coverage             |
| `npm run test:e2e`         | Playwright E2E (default config)     |
| `npm run test:e2e:ui`      | Playwright interactive UI mode      |
| `npm run test:smoke`       | Smoke tests against localhost       |
| `npm run test:collections` | Collections E2E suite               |
| `npm run test:perf`        | Performance benchmarks              |

See the `Makefile` for granular pipeline test targets (`make help` for the full list).

## Project Structure

```
medialake_user_interface/
├── src/
│   ├── api/                  # API client, hooks, query keys, types
│   ├── common/               # Auth context, helpers (logger, storage, tokens)
│   ├── components/           # Shared UI components
│   │   ├── asset/            # Asset detail views (image, video, audio)
│   │   ├── collections/      # Collection modals and tree view
│   │   ├── common/           # Buttons, tables, layout, sidebar, dialogs
│   │   ├── pipelines/        # Pipeline execution dialogs
│   │   ├── search/           # Facet search, filters, results
│   │   ├── settings/         # Admin settings, API keys, permissions
│   │   ├── shared/           # Asset cards, grid/table views, pagination
│   │   └── TopBar/           # Search bar, filters, chat, semantic toggle
│   ├── constants/            # App-wide constants (pagination, file sizes)
│   ├── contexts/             # React contexts (sidebar, theme, feature flags, etc.)
│   ├── features/             # Feature modules (domain-driven)
│   │   ├── assets/           # Asset explorer, facet filter panel
│   │   ├── chat/             # Chat sidebar
│   │   ├── collection-groups/# Collection group CRUD + detail pages
│   │   ├── dashboard/        # Dashboard grid, widgets, presets
│   │   ├── executions/       # Pipeline execution list + detail
│   │   ├── pipelines/        # Pipeline editor (xyflow), list, CRUD
│   │   ├── settings/         # Connectors, environments, integrations,
│   │   │                       permissions, roles, system, user management
│   │   └── upload/           # S3 uploader modal, path browser
│   ├── forms/                # Dynamic form system (react-hook-form + zod)
│   ├── hooks/                # App-level hooks (debounce, media, search, etc.)
│   ├── i18n/                 # i18next config + locale files
│   ├── mocks/                # MSW handlers for dev/test
│   ├── pages/                # Route-level page components
│   ├── permissions/          # CASL-based RBAC (ability factory, guards, hooks)
│   ├── routes/               # React Router config (lazy-loaded routes)
│   ├── services/             # Domain services (EventBridge validator)
│   ├── shared/               # Shared hooks, UI (error boundaries), node API
│   ├── stores/               # Zustand stores (search)
│   ├── styles/               # Global CSS (theme, player overrides)
│   ├── theme/                # MUI theme config + design tokens
│   ├── types/                # Shared TypeScript types
│   └── utils/                # Pure utility functions
├── tests/                    # Playwright E2E tests
│   ├── auth/                 # Cognito auth tests
│   ├── cloudfront/           # CloudFront login + tag discovery
│   ├── collections/          # Collection CRUD, sharing, groups, sub-collections
│   │   └── pages/            # Page object models
│   ├── connectors/           # Connector management tests
│   ├── fixtures/             # Playwright fixtures (auth, cognito, perf, S3, etc.)
│   ├── integration/          # CI integration tests (tag discovery, user lifecycle)
│   ├── performance/          # Page load, search, video player benchmarks
│   ├── pipelines/            # Pipeline import tests
│   ├── smoke/                # App smoke tests + permissions
│   ├── system/               # Semantic provider, region, search E2E
│   ├── user/                 # User management tests
│   └── utils/                # Test helpers (CloudFront resolver, Cognito adapter,
│                               AWS resource finder, search/upload helpers)
├── public/                   # Static assets
│   ├── aws-exports.json      # AWS Amplify config (Cognito + API endpoint)
│   └── feature-flags.json    # Runtime feature flags
├── scripts/                  # i18n validation scripts
├── playwright.config.ts      # Default Playwright config
├── playwright.ci.config.ts   # CI config (CloudFront, JUnit reporter)
├── playwright.collections.config.ts
├── playwright.perf.config.ts
├── playwright.pipelines.config.ts
├── playwright.smoke.config.ts
├── Makefile                  # Granular test runner targets
├── vite.config.ts            # Vite build config (chunk splitting, aliases)
├── vitest.config.ts          # Vitest unit test config
└── tsconfig.json             # TypeScript config (path alias: @/ → src/)
```

## Tech Stack

| Category        | Libraries                                                     |
| --------------- | ------------------------------------------------------------- |
| Framework       | React 19, TypeScript 5, Vite 7                                |
| UI              | MUI 7 (Material UI), Emotion, MUI X (date pickers, tree view) |
| Routing         | React Router 7 (lazy-loaded routes)                           |
| State           | Zustand 5 (client), TanStack Query 5 (server)                 |
| Tables          | TanStack Table 8, TanStack Virtual 3                          |
| Forms           | React Hook Form 7, Zod 4                                      |
| Auth            | AWS Amplify 6, Amazon Cognito                                 |
| i18n            | i18next 25, react-i18next 16                                  |
| Permissions     | CASL 6 (attribute-based access control)                       |
| Pipeline Editor | xyflow 12 (React Flow)                                        |
| Media Player    | Omakase Player 0.25                                           |
| File Upload     | Uppy 5 (S3 multipart)                                         |
| HTTP            | Axios                                                         |
| Unit Testing    | Vitest 4, Testing Library, MSW 2, vitest-axe                  |
| E2E Testing     | Playwright 1.52                                               |
| Linting         | ESLint 9 (flat config), typescript-eslint                     |
| Formatting      | Prettier 3 (enforced via Husky + lint-staged)                 |

## Architecture

### Authentication

AWS Cognito handles authentication. The app fetches `public/aws-exports.json` at startup to configure Amplify with the user pool, identity pool, and API endpoint. OAuth redirect URLs point to the CloudFront distribution.

### Routing & Code Splitting

All page components are lazy-loaded via `React.lazy()` with Suspense fallbacks. Routes are protected by `ProtectedRoute` (auth check) and `RoutePermissionGuard` (CASL permission check). The Vite build splits vendor chunks by domain (React, MUI, AWS, TanStack, xyflow, i18n, forms) for optimal caching.

### Permissions

RBAC is implemented with CASL. The permission system includes:

- `ability-factory.ts` — builds CASL abilities from user roles
- `RoutePermissionGuard` — blocks route access
- `<Can>` component — conditional rendering based on permissions
- `usePermission` / `useActionPermission` hooks

### Feature Flags

Runtime feature flags are loaded from `public/feature-flags.json` and provided via `FeatureFlagsContext`. Current flags: `advanced-permissions-enabled`, `chat-enabled`, `manual-pipeline-trigger-enabled`, `system-upgrades-enabled`.

### Internationalization

8 languages supported: English (default), German, Portuguese, French, Chinese, Hindi, Arabic, Hebrew. RTL layout is supported for Arabic and Hebrew via `DirectionContext`. Language detection uses the browser's navigator language.

### State Management

- Server state: TanStack Query with centralized query keys (`src/api/queryKeys.ts`)
- Client state: Zustand stores (search state)
- Form state: React Hook Form with Zod schema validation

## Testing

### Unit Tests (Vitest)

Unit tests live alongside source files in `src/` using the `*.test.ts` / `*.spec.ts` pattern.

```bash
npm run test              # Single run
npm run test:coverage     # With v8 coverage report
```

### E2E Tests (Playwright)

E2E tests are in `tests/` with separate Playwright configs per test suite. Each config has its own `testDir`, timeout, parallelism, and reporter settings.

| Config                             | Suite                    | Target                     |
| ---------------------------------- | ------------------------ | -------------------------- |
| `playwright.config.ts`             | Default (all tests)      | localhost:5173             |
| `playwright.ci.config.ts`          | CI integration           | CloudFront deployment      |
| `playwright.smoke.config.ts`       | Smoke tests              | localhost:5173             |
| `playwright.collections.config.ts` | Collections CRUD/sharing | CloudFront (auto-detected) |
| `playwright.pipelines.config.ts`   | Pipeline import/deploy   | CloudFront (auto-detected) |
| `playwright.perf.config.ts`        | Performance benchmarks   | CloudFront (auto-detected) |

CloudFront-targeting configs auto-detect the base URL via `tests/utils/cloudfront-url-resolver.ts` (SSM → tags → listing). Override with `PLAYWRIGHT_BASE_URL` env var.

```bash
# Smoke tests
npm run test:smoke

# Collections against a specific AWS profile
AWS_PROFILE=ml-dev2 npm run test:collections

# Pipeline tests with Makefile
make test-marengo3os profile=ml-uat4

# Performance benchmarks
npm run test:perf
```

## Code Quality

Pre-commit hooks (Husky + lint-staged) run Prettier and ESLint on staged files automatically.

```bash
npm run format             # Manual Prettier run on src/
```

ESLint uses the flat config format (`eslint.config.js`) with `typescript-eslint` recommended rules.

Prettier config: double quotes, 100 char width, trailing commas (ES5), 2-space indent.

## Environment Configuration

### `public/aws-exports.json`

Deployed by the backend CloudFormation stack. Contains:

- Cognito user pool ID, client ID, identity pool ID
- OAuth domain and redirect URLs
- REST API endpoint (CloudFront-proxied)

### `public/feature-flags.json`

Runtime feature toggles. Update this file to enable/disable features without redeploying.

### `.env` (optional)

Only needed for pipeline E2E tests that require third-party API keys:

```
TWELVELABS_API_KEY=...
COACTIVE_API_KEY=...
```

## Path Aliases

TypeScript and Vite are configured with `@/` → `src/`:

```typescript
import { usePermission } from "@/permissions/hooks/usePermission";
```

## Authors

- Robert Raver
- Lior Berezinski
