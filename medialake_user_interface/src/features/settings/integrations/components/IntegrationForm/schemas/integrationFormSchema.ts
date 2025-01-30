import { z } from 'zod';
import { createZodSchema } from '@/forms/utils/createZodSchema';
import { createIntegrationFormDefinition } from '@/features/settings/integrations/schemas/integrationFormDefinition';

// Create a default schema with empty environments array
// The actual schema with environments will be created in the component
export const integrationFormSchema = createZodSchema(
    createIntegrationFormDefinition([]).fields
);

export type IntegrationFormData = z.infer<typeof integrationFormSchema>;

export const createIntegrationFormDefaults = (): IntegrationFormData => ({
    nodeId: '',
    description: '',
    environmentId: '',
    auth: {
        type: 'apiKey',
        credentials: {},
    },
});
