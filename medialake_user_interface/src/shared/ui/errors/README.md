# Error Handling Components

This directory contains components for handling errors in the application.

## Available Components

### 1. ErrorBoundary

A component-level error boundary based on `react-error-boundary` that provides a user-friendly UI when a component throws an error.

#### Usage

```tsx
import { ErrorBoundary } from "@/shared/ui/errors";

const MyComponent = () => {
  return (
    <ErrorBoundary
      onReset={() => {
        // Reset the component state here
      }}
      onError={(error, info) => {
        // Log errors to your error reporting service
        console.error("Error caught by boundary:", error, info);
      }}
    >
      <MyPotentiallyBuggyComponent />
    </ErrorBoundary>
  );
};
```

#### Props

- `children`: React nodes to be rendered
- `fallbackRender`: Optional custom render function for the error state
- `onReset`: Optional callback called when the "Try Again" button is clicked
- `onError`: Optional callback called when an error is caught

### 2. RouteErrorBoundary

A specialized error boundary for use with React Router's `errorElement` prop. It automatically extracts error information from the Router context.

#### Usage in Router Configuration

```tsx
import { createBrowserRouter } from "react-router-dom";
import { RouteErrorBoundary } from "@/shared/ui/errors";

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootComponent />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        path: "dashboard",
        element: <Dashboard />,
        // You can also add an errorElement to individual routes
        errorElement: <RouteErrorBoundary />,
      },
    ],
  },
]);
```

## Best Practices

1. **Component-Level Errors**:
   - Wrap complex components with `<ErrorBoundary>` to prevent the entire app from crashing
   - For key UI sections, always use an ErrorBoundary

2. **Route-Level Errors**:
   - Use `errorElement: <RouteErrorBoundary />` on your routes to handle navigation and data loading errors
   - Consider adding more specific errorElements for important routes

3. **Async Error Handling**:
   - Use React Query's error handling for data fetching errors
   - Consider wrapping async components with ErrorBoundary

4. **Error Reporting**:
   - Use the `onError` callback to send errors to your monitoring service

## Example

See `features/ui/ExampleWithErrorHandling.tsx` for a complete working example.
