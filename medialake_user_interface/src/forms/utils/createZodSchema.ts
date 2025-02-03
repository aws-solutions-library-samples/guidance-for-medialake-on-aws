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
    const shape: Record<string, z.ZodTypeAny> = {};

    fields.forEach((field) => {
        const fieldName = field.name;
        let fieldSchema: z.ZodTypeAny;

        switch (field.type) {
            case 'number':
                fieldSchema = z.coerce.number();
                break;
            case 'switch':
                fieldSchema = z.boolean();
                break;
            case 'select':
            case 'multiselect':
                if (field.options) {
                    const values = field.options.map(opt => opt.value);
                    fieldSchema = field.type === 'multiselect'
                        ? z.array(z.string())
                        : z.string().refine(val => values.includes(val));
                } else {
                    fieldSchema = field.type === 'multiselect'
                        ? z.array(z.string())
                        : z.string();
                }
                break;
            case 'password':
            case 'email':
            case 'text':
            default:
                fieldSchema = z.string();
        }

        if (!field.required) {
            fieldSchema = fieldSchema.optional();
        }

        if (fieldName.startsWith('parameters.')) {
            const paramName = fieldName.replace('parameters.', '');
            if (!shape.parameters) {
                shape.parameters = z.object({}).passthrough();
            }
            (shape.parameters as z.ZodObject<any>).shape[paramName] = fieldSchema;
        } else {
            shape[fieldName] = fieldSchema;
        }
    });

    const schema = z.object(shape).passthrough();

    // Cache the schema using the fields reference
    schemaCache.set(fields, schema);
    
    return schema;
};
