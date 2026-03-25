import React, { createContext, useContext, useState, ReactNode } from "react";

// Define the structure of a chat message
export interface ChatMessage {
  id: string;
  content: string;
  sender: "user" | "system";
  timestamp: Date;
  isThinking?: boolean;
}

// Define the context type
interface ChatContextType {
  isOpen: boolean;
  messages: ChatMessage[];
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  addMessage: (content: string, sender: "user" | "system", isThinking?: boolean) => void;
  updateLastMessage: (content: string) => void;
  clearHistory: () => void;
}

// Create the context with a default undefined value
const ChatContext = createContext<ChatContextType | undefined>(undefined);

// Props for the provider component
interface ChatProviderProps {
  children: ReactNode;
}

// Provider component that will wrap the app
export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const openChat = React.useCallback(() => setIsOpen(true), []);
  const closeChat = React.useCallback(() => setIsOpen(false), []);
  const toggleChat = React.useCallback(() => setIsOpen((prev) => !prev), []);

  const addMessage = React.useCallback(
    (content: string, sender: "user" | "system", isThinking: boolean = false) => {
      const newMessage: ChatMessage = {
        id: Date.now().toString(),
        content,
        sender,
        timestamp: new Date(),
        isThinking,
      };
      setMessages((prevMessages) => [...prevMessages, newMessage]);
    },
    []
  );

  const updateLastMessage = React.useCallback((content: string) => {
    setMessages((prevMessages) => {
      if (prevMessages.length === 0) return prevMessages;
      const updatedMessages = [...prevMessages];
      const lastMessage = { ...updatedMessages[updatedMessages.length - 1] };
      lastMessage.content = content;
      lastMessage.isThinking = false;
      updatedMessages[updatedMessages.length - 1] = lastMessage;
      return updatedMessages;
    });
  }, []);

  const clearHistory = React.useCallback(() => setMessages([]), []);

  const value = React.useMemo(
    () => ({
      isOpen,
      messages,
      openChat,
      closeChat,
      toggleChat,
      addMessage,
      updateLastMessage,
      clearHistory,
    }),
    [isOpen, messages, openChat, closeChat, toggleChat, addMessage, updateLastMessage, clearHistory]
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};

// Custom hook to use the chat context
export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
};

export default ChatContext;
