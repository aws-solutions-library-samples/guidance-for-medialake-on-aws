import { useState } from 'react';
import { UseMutationResult } from '@tanstack/react-query';

type ApiStatus = {
    show: boolean;
    status: 'idle' | 'loading' | 'success' | 'error';
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
        status: 'idle',
        action: '',
        message: '',
    });

    const handleMutation = async <TMutData = TData, TMutError = TError, TMutVariables = TVariables>(
        options: UseApiMutationHandlerOptions<TMutData, TMutError, TMutVariables>,
        variables: TMutVariables
    ) => {
        const { mutation, actionMessages, onSuccess, onError } = options;

        setApiStatus({
            show: true,
            status: 'loading',
            action: actionMessages.loading,
            message: undefined,
        });

        try {
            const result = await mutation.mutateAsync(variables);
            setApiStatus({
                show: true,
                status: 'success',
                action: actionMessages.success,
                message: actionMessages.successMessage || 'Operation completed successfully.',
            });
            if (onSuccess) {
                onSuccess(result);
            }
            return result; // Allow chaining or further actions
        } catch (error) {
            const typedError = error as TMutError; // Cast error
            const errorMessage = typedError instanceof Error ? typedError.message : 'An unknown error occurred.';
            console.error(`${actionMessages.error}:`, error); // Log the original error

            setApiStatus({
                show: true,
                status: 'error',
                action: actionMessages.error,
                message: errorMessage,
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
            status: 'idle',
            action: '',
            message: '',
        });
    }

    const closeApiStatus = () => {
        setApiStatus(prev => ({ ...prev, show: false }));
    };

    return {
        apiStatus,
        handleMutation,
        resetApiStatus,
        closeApiStatus, // Expose close function separately if needed
    };
}; 