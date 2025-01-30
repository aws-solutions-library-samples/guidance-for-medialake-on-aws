import { z } from 'zod';
import { FormFieldDefinition } from '../types';

const createFieldSchema = (field: FormFieldDefinition) => {
    let fieldSchema: z.ZodString | z.ZodNumber | z.ZodArray<z.ZodString> | z.ZodEnum<[string, ...string[]]>;

    switch (field.validation?.type) {
        case 'string':
            let stringSchema = z.string();
            field.validation.rules.forEach(rule => {
                switch (rule.type) {
                    case 'min':
                        stringSchema = stringSchema.min(
                            Number(rule.value),
                            rule.message
                        );
                        break;
                    case 'email':
                        stringSchema = stringSchema.email(rule.message);
                        break;
                    case 'url':
                        stringSchema = stringSchema.url(rule.message);
                        break;
                    case 'regex':
                        if (typeof rule.value === 'string') {
                            stringSchema = stringSchema.regex(
                                new RegExp(rule.value),
                                rule.message
                            );
                        }
                        break;
                }
            });
            fieldSchema = stringSchema;
            break;

        case 'array':
            let arraySchema = z.array(z.string());
            field.validation.rules.forEach(rule => {
                if (rule.type === 'min') {
                    arraySchema = arraySchema.min(
                        Number(rule.value),
                        rule.message
                    );
                }
            });
            fieldSchema = arraySchema;
            break;

        case 'number':
            let numberSchema = z.number();
            field.validation?.rules.forEach(rule => {
                switch (rule.type) {
                    case 'min':
                        numberSchema = numberSchema.min(
                            Number(rule.value),
                            rule.message
                        );
                        break;
                    case 'max':
                        numberSchema = numberSchema.max(
                            Number(rule.value),
                            rule.message
                        );
                        break;
                }
            });
            fieldSchema = numberSchema;
            break;

        default:
            if (field.type === 'select' && field.options) {
                const values = field.options.map(opt => opt.value);
                fieldSchema = z.enum(values as [string, ...string[]]);
            } else {
                fieldSchema = z.string();
            }
    }

    return field.required ? fieldSchema : fieldSchema.optional();
};

const buildNestedSchema = (fields: FormFieldDefinition[]) => {
    // Group fields by their parent path
    const fieldGroups = fields.reduce((acc, field) => {
        const parts = field.name.split('.');
        const parentPath = parts.slice(0, -1).join('.');
        const fieldName = parts[parts.length - 1];

        if (!acc[parentPath]) {
            acc[parentPath] = [];
        }
        acc[parentPath].push({ ...field, name: fieldName });
        return acc;
    }, {} as Record<string, FormFieldDefinition[]>);

    // Build schema recursively
    const buildSchema = (path: string): z.ZodTypeAny => {
        const fields = fieldGroups[path] || [];
        const shape: Record<string, z.ZodTypeAny> = {};

        fields.forEach(field => {
            const fullPath = path ? `${path}.${field.name}` : field.name;

            // If this field has children, create a nested object
            if (fieldGroups[fullPath]) {
                shape[field.name] = buildSchema(fullPath);
            } else {
                shape[field.name] = createFieldSchema(field);
            }
        });

        return z.object(shape).strict();
    };

    return buildSchema('');
};

export const createZodSchema = (fields: FormFieldDefinition[]) => {
    return buildNestedSchema(fields);
};
