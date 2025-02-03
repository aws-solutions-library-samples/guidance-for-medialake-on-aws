import React from 'react';
import { Box, Button } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Form } from './Form';
import { FormField } from './FormField';
import { FormSelect } from './FormSelect';
import { FormSwitch } from './FormSwitch';
import { useFormWithValidation } from '../hooks/useFormWithValidation';
import { FormDefinition, FormFieldDefinition } from '../types';
import { createZodSchema } from '../utils/createZodSchema';

interface DynamicFormProps {
    definition: FormDefinition;
    defaultValues?: Record<string, any>;
    onSubmit: (data: any) => Promise<void>;
    onCancel?: () => void;
    onBack?: () => void;
    showButtons?: boolean;
}

export const DynamicForm: React.FC<DynamicFormProps> = ({
    definition,
    defaultValues,
    onSubmit,
    onCancel,
    onBack,
    showButtons = true,
}) => {
    const { t } = useTranslation();
    const schema = React.useMemo(
        () => createZodSchema(definition.fields),
        [definition.fields]
    );

    const form = useFormWithValidation({
        validationSchema: schema,
        defaultValues,
        translationPrefix: definition.translationPrefix,
    });

    const renderField = (field: FormFieldDefinition) => {
        // Skip fields that should be hidden based on conditions
        if (field.showWhen) {
            const dependentValue = form.watch(field.showWhen.field);
            if (dependentValue !== field.showWhen.value) {
                return null;
            }
        }

        switch (field.type) {
            case 'select':
                return (
                    <FormSelect
                        key={field.name}
                        name={field.name}
                        control={form.control}
                        label={field.label}
                        tooltip={field.tooltip}
                        options={field.options || []}
                        required={field.required}
                        translationPrefix={definition.translationPrefix}
                    />
                );

            case 'multiselect':
                return (
                    <FormSelect
                        key={field.name}
                        name={field.name}
                        control={form.control}
                        label={field.label}
                        tooltip={field.tooltip}
                        options={field.options || []}
                        multiple
                        required={field.required}
                        translationPrefix={definition.translationPrefix}
                    />
                );

            case 'switch':
                return (
                    <FormSwitch
                        key={field.name}
                        name={field.name}
                        control={form.control}
                        label={field.label}
                        tooltip={field.tooltip}
                        translationPrefix={definition.translationPrefix}
                    />
                );

            default:
                return (
                    <FormField
                        key={field.name}
                        name={field.name}
                        control={form.control}
                        label={field.label}
                        tooltip={field.tooltip}
                        type={field.type}
                        required={field.required}
                        translationPrefix={definition.translationPrefix}
                    />
                );
        }
    };

    return (
        <Form form={form} onSubmit={onSubmit} onCancel={onCancel} showButtons={showButtons}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {definition.fields.map(renderField)}
            </Box>
        </Form>
    );
};
