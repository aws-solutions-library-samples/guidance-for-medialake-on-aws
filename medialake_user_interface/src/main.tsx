import React from 'react'
import ReactDOM from 'react-dom/client'
import AppConfigured from "./components/app-configured";
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'

// Create a client
const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <AppConfigured />
        </QueryClientProvider>
    </React.StrictMode>
)

