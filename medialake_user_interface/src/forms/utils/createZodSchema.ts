import { z } from 'zod';
import { FormFieldDefinition } from '../types';

// Create a WeakMap to store schemas using the fields array reference itself as the key
const schemaCache = new WeakMap<FormFieldDefinition[], z.ZodType>();

export const createZodSchema = (fields: FormFieldDefinition[]) => {
    // Check if we have a cached schema using the fields reference
    if (schemaCache.has(fields)) {
        return schemaCache.get(fields)!;
    }

    // If not in cache, create new schema
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

    const schema = z.object({
        parameters: z.object(parametersShape).passthrough()
    }).passthrough();

    // Cache the schema using the fields reference
    schemaCache.set(fields, schema);
    
    return schema;
};
