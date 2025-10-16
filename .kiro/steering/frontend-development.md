---
inclusion: fileMatch
fileMatchPattern: "medialake_user_interface/**/*"
---

# Frontend Development Guidelines for MediaLake

## Technology Stack Overview

MediaLake's frontend is built with modern React and TypeScript, providing a responsive and intuitive user interface for media management and processing workflows.

### Core Technologies

- **React 18** with TypeScript for component development
- **Vite** for fast development and optimized builds
- **React Router** for client-side routing
- **Material-UI (MUI)** for consistent design system
- **React Query/TanStack Query** for server state management
- **Playwright** for end-to-end testing

## Project Structure Standards

### Directory Organization

```
medialake_user_interface/src/
├── api/              # API service layer and client
├── app/              # Application-level configuration
├── components/       # Reusable UI components
├── features/         # Feature-based modules
├── hooks/            # Custom React hooks
├── pages/            # Page-level components
├── shared/           # Shared utilities and types
├── stores/           # State management
├── styles/           # Global styles and themes
├── types/            # TypeScript type definitions
└── utils/            # Utility functions
```

### Feature-Based Architecture

Organize code by features rather than technical layers:

```
src/features/assets/
├── components/       # Asset-specific components
├── hooks/           # Asset-related hooks
├── services/        # Asset API services
├── types/           # Asset type definitions
└── utils/           # Asset utility functions
```

## Component Development Standards

### Component Structure

```typescript
// Example component structure
import React from 'react';
import { Box, Typography } from '@mui/material';
import { AssetCardProps } from './types';

export const AssetCard: React.FC<AssetCardProps> = ({
  asset,
  onSelect,
  ...props
}) => {
  return (
    <Box {...props}>
      <Typography variant="h6">{asset.title}</Typography>
      {/* Component implementation */}
    </Box>
  );
};

// Export types alongside components
export type { AssetCardProps } from './types';
```

### TypeScript Best Practices

- Use strict TypeScript configuration
- Define interfaces for all props and data structures
- Use generic types for reusable components
- Implement proper error boundaries with typed error handling

### Component Naming

- Use PascalCase for component names
- Use descriptive names that indicate purpose
- Prefix custom hooks with 'use'
- Use kebab-case for file names

## State Management Patterns

### Local State

- Use React hooks (useState, useReducer) for component-local state
- Implement custom hooks for complex local state logic
- Use useCallback and useMemo for performance optimization

### Server State

- Use React Query/TanStack Query for server state management
- Implement proper caching strategies
- Handle loading and error states consistently
- Use optimistic updates where appropriate

### Global State

- Use React Context for truly global state
- Implement state providers at appropriate levels
- Use reducers for complex state transitions
- Consider state management libraries for complex applications

## API Integration Standards

### Service Layer Pattern

```typescript
// api/services/assetService.ts
import { apiClient } from "../client";
import { Asset, CreateAssetRequest } from "../types";

export const assetService = {
  getAssets: async (): Promise<Asset[]> => {
    const response = await apiClient.get("/assets");
    return response.data;
  },

  createAsset: async (data: CreateAssetRequest): Promise<Asset> => {
    const response = await apiClient.post("/assets", data);
    return response.data;
  },

  // Additional service methods
};
```

### Error Handling

- Implement consistent error handling across all API calls
- Use error boundaries for component-level error handling
- Provide user-friendly error messages
- Log errors for debugging and monitoring

### Loading States

- Implement consistent loading indicators
- Use skeleton screens for better user experience
- Handle partial loading states appropriately
- Provide feedback for long-running operations

## UI/UX Standards

### Design System

- Use Material-UI components consistently
- Implement custom theme configuration
- Follow accessibility guidelines (WCAG 2.1)
- Maintain consistent spacing and typography

### Responsive Design

- Use Material-UI's responsive breakpoints
- Test on multiple screen sizes and devices
- Implement mobile-first design approach
- Use flexible layouts with CSS Grid and Flexbox

### User Experience

- Provide clear navigation and breadcrumbs
- Implement proper form validation and feedback
- Use progressive disclosure for complex interfaces
- Maintain consistent interaction patterns

## Performance Optimization

### Code Splitting

- Use React.lazy for route-based code splitting
- Implement component-level code splitting where beneficial
- Use dynamic imports for large dependencies
- Monitor bundle sizes and optimize accordingly

### Rendering Optimization

- Use React.memo for expensive components
- Implement proper key props for list rendering
- Use useCallback and useMemo appropriately
- Avoid unnecessary re-renders through proper state design

### Asset Optimization

- Optimize images and media assets
- Use appropriate image formats (WebP, AVIF)
- Implement lazy loading for images and components
- Use CDN for static asset delivery

## Testing Standards

### Component Testing

- Test component behavior, not implementation details
- Use React Testing Library for component tests
- Test user interactions and accessibility
- Mock external dependencies appropriately

### Integration Testing

- Use Playwright for end-to-end testing
- Test complete user workflows
- Include error scenarios in tests
- Maintain test data fixtures

### Testing Utilities

```typescript
// tests/utils/testUtils.tsx
import { render, RenderOptions } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

export const renderWithProviders = (
  ui: React.ReactElement,
  options?: RenderOptions
) => {
  const queryClient = createTestQueryClient();

  const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );

  return render(ui, { wrapper: Wrapper, ...options });
};
```

## Security Best Practices

### Authentication Integration

- Integrate with AWS Cognito for authentication
- Handle token refresh automatically
- Implement proper logout functionality
- Store tokens securely

### Input Validation

- Validate all user inputs on the client side
- Sanitize data before sending to APIs
- Use proper form validation libraries
- Implement CSRF protection

### Content Security

- Implement proper Content Security Policy (CSP)
- Sanitize user-generated content
- Use HTTPS for all communications
- Validate file uploads on the client side

## Build and Deployment

### Build Configuration

- Use Vite for fast development and optimized production builds
- Configure proper environment variables
- Implement build-time optimizations
- Use proper source maps for debugging

### Environment Management

- Use environment-specific configuration files
- Implement feature flags for gradual rollouts
- Use proper secrets management
- Configure different API endpoints per environment

### Deployment Pipeline

- Use automated deployment pipelines
- Implement proper testing stages
- Use CloudFront for global content delivery
- Monitor deployment success and rollback if needed

## Accessibility Standards

### WCAG Compliance

- Follow WCAG 2.1 AA guidelines
- Use semantic HTML elements
- Implement proper ARIA attributes
- Ensure keyboard navigation support

### Testing Accessibility

- Use automated accessibility testing tools
- Test with screen readers
- Verify keyboard-only navigation
- Include accessibility in code reviews

## Internationalization (i18n)

### Implementation

- Use react-i18next for internationalization
- Organize translation files by feature
- Implement proper pluralization rules
- Support right-to-left (RTL) languages

### Content Management

- Use translation keys consistently
- Implement proper fallback mechanisms
- Support dynamic content translation
- Maintain translation file versioning

## Development Workflow

### Code Quality

- Use ESLint and Prettier for code formatting
- Implement pre-commit hooks for quality checks
- Use TypeScript strict mode
- Maintain consistent code style

### Development Tools

- Use React Developer Tools for debugging
- Implement proper logging for development
- Use Storybook for component development
- Set up hot module replacement for fast development

### Documentation

- Document component APIs and usage
- Maintain README files for each feature
- Use JSDoc comments for complex functions
- Keep architectural decision records (ADRs)
