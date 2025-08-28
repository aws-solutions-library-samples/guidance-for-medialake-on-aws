import React, { useState } from "react";
import { Button, Card, CardContent, Typography, Box } from "@mui/material";
import { ErrorBoundary } from "@/shared/ui/errors";

// Example of a component that might throw an error
const BuggyCounter: React.FC = () => {
  const [counter, setCounter] = useState(0);

  const handleIncrement = () => {
    // This will throw when counter reaches 5
    if (counter === 5) {
      throw new Error("Counter reached 5!");
    }
    setCounter(counter + 1);
  };

  return (
    <Box textAlign="center">
      <Typography variant="h6" mb={2}>
        Counter Value: {counter}
      </Typography>
      <Button variant="contained" color="primary" onClick={handleIncrement}>
        Increment
      </Button>
      <Typography variant="body2" mt={2} color="text.secondary">
        (The counter will throw an error when it reaches 5)
      </Typography>
    </Box>
  );
};

// Example of how to use the ErrorBoundary component
const ExampleWithErrorHandling: React.FC = () => {
  const [key, setKey] = useState(0);

  // This will be passed to the ErrorBoundary to reset its state
  const handleReset = () => {
    setKey((prevKey) => prevKey + 1);
  };

  return (
    <Card sx={{ maxWidth: 500, mx: "auto", mt: 4 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Error Boundary Example
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          This example demonstrates how to use the ErrorBoundary component to
          capture and display errors.
        </Typography>

        {/*
          The key prop ensures the component is re-mounted when reset
          onReset is called by the error boundary when the "Try Again" button is clicked
        */}
        <ErrorBoundary
          key={key}
          onReset={handleReset}
          onError={(error, info) => {
            // You could log errors to your error reporting service here
            console.log("Captured error:", error, info);
          }}
        >
          <BuggyCounter />
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
};

export default ExampleWithErrorHandling;
