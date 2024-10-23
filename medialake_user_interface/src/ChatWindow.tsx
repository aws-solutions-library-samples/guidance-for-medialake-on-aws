import React, { useState, useEffect, useCallback } from 'react';
import { Box, TextField, Button, Typography, IconButton } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';

interface Message {
    text: string;
}

interface ChatWindowProps {
    chatId: string;
}

function ChatWindow({ chatId }: ChatWindowProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputMessage, setInputMessage] = useState('');
    const [socket, setSocket] = useState<WebSocket | null>(null);

    const connectWebSocket = useCallback(() => {
        const ws = new WebSocket('wss://your-api-gateway-endpoint.execute-api.region.amazonaws.com/production');

        ws.onopen = () => {
            console.log('Connected to WebSocket');
            ws.send(JSON.stringify({ action: 'joinRoom', chatId }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'message') {
                setMessages((prevMessages) => [...prevMessages, data.message]);
            }
        };

        ws.onclose = () => {
            console.log('Disconnected from WebSocket');
            setTimeout(connectWebSocket, 3000); // Attempt to reconnect after 3 seconds
        };

        setSocket(ws);
    }, [chatId]);

    useEffect(() => {
        connectWebSocket();

        return () => {
            if (socket) {
                socket.close();
            }
        };
    }, [connectWebSocket, socket]);

    const sendMessage = (e: React.FormEvent) => {
        e.preventDefault();
        if (inputMessage.trim() && socket) {
            const message = {
                action: 'sendMessage',
                chatId,
                message: inputMessage,
            };
            socket.send(JSON.stringify(message));
            setInputMessage('');
        }
    };

    return (
        <Box sx={{ bgcolor: 'background.paper', height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ p: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
                <Typography variant="h6">Global Chat</Typography>
                <IconButton onClick={() => window.history.back()} size="small">
                    <CloseIcon />
                </IconButton>
            </Box>
            <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 1 }}>
                {messages.map((msg, index) => (
                    <Typography key={index} paragraph>
                        {msg.text}
                    </Typography>
                ))}
            </Box>
            <Box component="form" onSubmit={sendMessage} sx={{ p: 1, borderTop: 1, borderColor: 'divider' }}>
                <TextField
                    fullWidth
                    size="small"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder="Type a message..."
                    sx={{ mb: 1 }}
                />
                <Button type="submit" variant="contained" fullWidth>
                    Send
                </Button>
            </Box>
        </Box>
    );
}

export default ChatWindow;
