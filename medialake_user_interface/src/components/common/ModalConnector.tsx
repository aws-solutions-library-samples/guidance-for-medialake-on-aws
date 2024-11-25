import React, { createContext, useContext, useState, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

interface ModalContextType {
    showModal: (content: ReactNode, options?: ModalOptions) => void;
    hideModal: () => void;
}

interface ModalOptions {
    title?: string;
    onConfirm?: () => void;
    onCancel?: () => void;
    confirmText?: string;
    cancelText?: string;
}

interface ModalProviderProps {
    children: ReactNode;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export const ModalProvider: React.FC<ModalProviderProps> = ({ children }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [modalContent, setModalContent] = useState<ReactNode | null>(null);
    const [modalOptions, setModalOptions] = useState<ModalOptions>({});
    const { t } = useTranslation();

    const showModal = (content: ReactNode, options: ModalOptions = {}) => {
        setModalContent(content);
        setModalOptions(options);
        setIsOpen(true);
    };

    const hideModal = () => {
        setIsOpen(false);
        setModalContent(null);
        setModalOptions({});
    };

    return (
        <ModalContext.Provider value={{ showModal, hideModal }}>
            {children}
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center">
                    <div className="fixed inset-0 bg-black opacity-50" onClick={hideModal}></div>
                    <div className="relative bg-white rounded-lg p-6 max-w-lg w-full mx-4">
                        {modalOptions.title && (
                            <h2 className="text-xl font-semibold mb-4">{modalOptions.title}</h2>
                        )}
                        <div className="mb-6">{modalContent}</div>
                        <div className="flex justify-end space-x-2">
                            {modalOptions.onCancel && (
                                <button
                                    onClick={() => {
                                        modalOptions.onCancel?.();
                                        hideModal();
                                    }}
                                    className="px-4 py-2 border rounded-md hover:bg-gray-100"
                                >
                                    {modalOptions.cancelText || t('common.cancel')}
                                </button>
                            )}
                            {modalOptions.onConfirm && (
                                <button
                                    onClick={() => {
                                        modalOptions.onConfirm?.();
                                        hideModal();
                                    }}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                                >
                                    {modalOptions.confirmText || t('common.save')}
                                </button>
                            )}
                            {!modalOptions.onConfirm && !modalOptions.onCancel && (
                                <button
                                    onClick={hideModal}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                                >
                                    {t('common.close')}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </ModalContext.Provider>
    );
};

export const useModal = () => {
    const context = useContext(ModalContext);
    if (context === undefined) {
        throw new Error('useModal must be used within a ModalProvider');
    }
    return context;
};

export default ModalProvider;
