import { z } from 'zod';
import { FormFieldDefinition } from '../types';

export const createZodSchema = (fields: FormFieldDefinition[]) => {
    console.log('[createZodSchema] Creating schema for fields:', fields);
    
    const parametersShape: Record<string, any> = {};

    fields.forEach((field) => {
        const fieldName = field.name;
        if (fieldName.startsWith('parameters.')) {
            const paramName = fieldName.replace('parameters.', '');
            let fieldSchema = z.string();

            switch (field.type) {
                case 'number':
                    fieldSchema = z.coerce.number();
                    break;
                case 'boolean':
                case 'switch':
                    fieldSchema = z.boolean();
                    break;
                case 'select':
                    if (field.options) {
                        fieldSchema = z.string();
                    }
                    break;
                default:
                    fieldSchema = z.string();
            }

            if (!field.required) {
                fieldSchema = fieldSchema.optional();
            }

            parametersShape[paramName] = fieldSchema;
        }
    });

    return z.object({
        parameters: z.object(parametersShape).passthrough()
    }).passthrough();
};
