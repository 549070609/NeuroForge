import { useState, useEffect, useRef, useCallback } from 'react';
import { api, ModelInfo, Session, Message } from './api';

// ============ Types ============

interface ChatMessage extends Message {
  id: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
}

interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

// ============ Main App Component ============

function App() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('glm-4-flash');
  const [sessions, setSessions] = useState<string[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chatAreaRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ============ Effects ============

  // Load models on mount
  useEffect(() => {
    api.listModels().then(setModels).catch(console.error);
  }, []);

  // Load sessions on mount
  useEffect(() => {
    refreshSessions();
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  // ============ Callbacks ============

  const refreshSessions = useCallback(async () => {
    try {
      const result = await api.listSessions();
      setSessions(result.sessions);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  }, []);

  const createNewSession = useCallback(async () => {
    try {
      setError(null);
      const session = await api.createSession({
        model: selectedModel,
        system_prompt: '你是一个有帮助的 AI 助手。',
      });
      setCurrentSession(session);
      setMessages([]);
      setSessions(prev => [session.session_id, ...prev]);

      // Connect WebSocket
      connectWebSocket(session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
    }
  }, [selectedModel]);

  const connectWebSocket = useCallback((sessionId: string) => {
    // Close existing connection
    wsRef.current?.close();

    const ws = api.createWebSocket(sessionId);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setIsConnected(false);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data);
    };
  }, []);

  const handleWebSocketMessage = useCallback((data: Record<string, unknown>) => {
    const type = data.type as string;

    switch (type) {
      case 'start':
        // Add typing indicator
        setIsLoading(true);
        break;

      case 'stream':
        // Handle nested stream events from run_stream
        const streamEvent = data.event as Record<string, unknown> | undefined;
        if (streamEvent && streamEvent.type === 'text' && typeof streamEvent.text === 'string') {
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + streamEvent.text }
              ];
            }
            return [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: 'assistant' as const,
                content: streamEvent.text,
                timestamp: new Date(),
              }
            ];
          });
        }
        break;

      case 'text':
        // Update last assistant message
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + (data.text as string) }
            ];
          }
          return [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant' as const,
              content: data.text as string,
              timestamp: new Date(),
            }
          ];
        });
        break;

      case 'tool_use':
        // Add tool call info
        setMessages(prev => {
          const last = prev[prev.length - 1];
          const toolCall: ToolCall = {
            id: data.id as string,
            name: data.name as string,
            input: data.input as Record<string, unknown>,
          };
          if (last?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...last, toolCalls: [...(last.toolCalls || []), toolCall] }
            ];
          }
          return prev;
        });
        break;

      case 'tool_result':
        // Add tool result message
        setMessages(prev => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'system' as const,
            content: `[Tool Result] ${data.name || 'unknown'}: ${typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2)}`,
            timestamp: new Date(),
          }
        ]);
        break;

      case 'end':
        setIsLoading(false);
        break;

      case 'error':
        setIsLoading(false);
        setError(data.message as string);
        break;

      default:
        console.log('Unknown message type:', type, data);
    }
  }, []);

  const sendMessage = useCallback(async () => {
    if (!inputValue.trim() || isLoading) return;

    const messageText = inputValue.trim();
    setInputValue('');

    // Add user message to UI
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: messageText,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);

    // Check if WebSocket is connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Send via WebSocket
      wsRef.current.send(JSON.stringify({ message: messageText }));
      setIsLoading(true);
    } else if (currentSession) {
      // Fallback to HTTP
      try {
        setIsLoading(true);
        const response = await api.sendMessage(currentSession.session_id, {
          message: messageText,
        });

        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.content,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMessage]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message');
      } finally {
        setIsLoading(false);
      }
    } else {
      setError('No active session. Please create a new session.');
    }
  }, [inputValue, isLoading, currentSession]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }, [sendMessage]);

  const selectSession = useCallback(async (sessionId: string) => {
    try {
      const session = await api.getSession(sessionId);
      setCurrentSession(session);

      // Load messages
      if (session.messages) {
        setMessages(session.messages.map((msg, i) => ({
          ...msg,
          id: `${sessionId}-${i}`,
          timestamp: new Date(),
        })));
      }

      // Connect WebSocket
      connectWebSocket(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
    }
  }, [connectWebSocket]);

  // ============ Render ============

  return (
    <div className="app">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>PyAgentForge</h1>
          <p>GLM Provider Test</p>

          <div className="model-selector">
            <label>Model</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
            >
              {models.map(model => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="session-list">
          {sessions.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '20px', fontSize: '0.875rem' }}>
              No sessions yet
            </div>
          ) : (
            sessions.map(sessionId => (
              <div
                key={sessionId}
                className={`session-item ${currentSession?.session_id === sessionId ? 'active' : ''}`}
                onClick={() => selectSession(sessionId)}
              >
                <div className="session-item-header">
                  <span className="session-id">{sessionId.slice(0, 8)}...</span>
                  <span className="session-status">active</span>
                </div>
              </div>
            ))
          )}
        </div>

        <button className="new-session-btn" onClick={createNewSession}>
          + New Session
        </button>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {/* Header */}
        <div className="header">
          <h2>{currentSession ? `Session: ${currentSession.session_id.slice(0, 8)}...` : 'No Session'}</h2>
          <div className="status-indicator">
            <span className={`status-dot ${isConnected ? 'connected' : ''}`} />
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div style={{
            padding: '12px 24px',
            backgroundColor: 'rgba(248, 113, 113, 0.1)',
            borderBottom: '1px solid var(--error)',
            color: 'var(--error)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--error)',
                cursor: 'pointer',
              }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Chat Area */}
        <div className="chat-area" ref={chatAreaRef}>
          {!currentSession ? (
            <div className="empty-state">
              <h3>Welcome to PyAgentForge</h3>
              <p>Create a new session to start testing</p>
            </div>
          ) : (
            <>
              {messages.map(msg => (
                <div key={msg.id} className={`message ${msg.role}`}>
                  <div className="message-header">
                    <span>{msg.role}</span>
                    <span>{msg.timestamp.toLocaleTimeString()}</span>
                  </div>
                  <div className="message-content">
                    {msg.content}
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="tool-call">
                        <span className="tool-name">Tool Calls:</span>
                        <ul style={{ margin: '4px 0 0 16px' }}>
                          {msg.toolCalls.map(tc => (
                            <li key={tc.id}>
                              <strong>{tc.name}</strong>
                              <pre style={{ margin: '4px 0', fontSize: '0.75rem' }}>
                                {JSON.stringify(tc.input, null, 2)}
                              </pre>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="message assistant">
                  <div className="typing-indicator">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="input-area">
          <div className="input-container">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
              disabled={!currentSession || isLoading}
              rows={1}
            />
            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={!inputValue.trim() || !currentSession || isLoading}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
