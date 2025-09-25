import { useState } from "react";
import { UseMutationResult } from "@tanstack/react-query";

type ApiStatus = {
  show: boolean;
  status: "idle" | "loading" | "success" | "error";
  action: string; // e.g., 'Creating User', 'Deleting Role'
  message?: string;
};

interface UseApiMutationHandlerOptions<TData, TError, TVariables> {
  mutation: UseMutationResult<TData, TError, TVariables>;
  actionMessages: {
    loading: string; // e.g., 'Creating user...'
    success: string; // e.g., 'User Created'
    successMessage?: string; // Optional success detail message
    error: string; // e.g., 'User Creation Failed'
  };
  onSuccess?: (data: TData) => void;
  onError?: (error: TError) => void;
}

export const useApiMutationHandler = <
  TData = unknown,
  TError = Error, // Default error type to standard Error
  TVariables = void,
>() => {
  const [apiStatus, setApiStatus] = useState<ApiStatus>({
    show: false,
    status: "idle",
    action: "",
    message: "",
  });

  const handleMutation = async <
    TMutData = TData,
    TMutError = TError,
    TMutVariables = TVariables,
  >(
    options: UseApiMutationHandlerOptions<TMutData, TMutError, TMutVariables>,
    variables: TMutVariables,
  ) => {
    const { mutation, actionMessages, onSuccess, onError } = options;

    setApiStatus({
      show: true,
      status: "loading",
      action: actionMessages.loading,
      message: undefined,
    });

    try {
      const result = await mutation.mutateAsync(variables);
      setApiStatus({
        show: true,
        status: "success",
        action: actionMessages.success,
        message:
          actionMessages.successMessage || "Operation completed successfully.",
      });
      if (onSuccess) {
        onSuccess(result);
      }
      return result; // Allow chaining or further actions
    } catch (error) {
      const typedError = error as TMutError; // Cast error
      console.error(`${actionMessages.error}:`, error); // Log the original error

      let displayMessage = "An unknown error occurred.";

      // Check if it looks like an Axios error with a response body
      if (
        typeof typedError === "object" &&
        typedError !== null &&
        "response" in typedError
      ) {
        const response = (typedError as any).response;
        if (response?.data) {
          try {
            let responseData = response.data;
            // Attempt to parse if data is a string (API Gateway sometimes does this)
            if (typeof responseData === "string") {
              responseData = JSON.parse(responseData);
            }
            // Check if parsed data has a message property
            if (
              typeof responseData === "object" &&
              responseData !== null &&
              "message" in responseData
            ) {
              displayMessage = responseData.message || displayMessage;
            } else if (typeof responseData === "string") {
              // If after parsing it's just a string, use that
              displayMessage = responseData;
            } else if (response?.statusText) {
              // Fallback to status text if no message in body
              displayMessage = response.statusText;
            }
          } catch (parseError) {
            console.error("Failed to parse error response data:", parseError);
            // Fallback if parsing fails or data is not as expected
            if (response?.statusText) {
              displayMessage = response.statusText;
            } else if (typedError instanceof Error) {
              displayMessage = typedError.message;
            }
          }
        } else if (response?.statusText) {
          // Use status text if no data field
          displayMessage = response.statusText;
        } else if (typedError instanceof Error) {
          displayMessage = typedError.message;
        }
      } else if (typedError instanceof Error) {
        // Standard Error object
        displayMessage = typedError.message;
      }

      setApiStatus({
        show: true,
        status: "error",
        action: actionMessages.error,
        message: displayMessage, // Use the extracted or default message
      });
      if (onError) {
        onError(typedError);
      }
      // Re-throw the error if the caller needs to handle it further
      // Or return null/undefined if preferred
      throw error;
    }
  };

  const resetApiStatus = () => {
    setApiStatus({
      show: false,
      status: "idle",
      action: "",
      message: "",
    });
  };

  const closeApiStatus = () => {
    setApiStatus((prev) => ({ ...prev, show: false }));
  };

  return {
    apiStatus,
    handleMutation,
    resetApiStatus,
    closeApiStatus, // Expose close function separately if needed
  };
};
