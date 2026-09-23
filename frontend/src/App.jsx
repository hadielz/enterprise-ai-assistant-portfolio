import { useEffect, useState } from "react";
import AuthScreen from "./AuthScreen";
import {
  API_BASE_URL,
  authenticatedFetch,
  clearToken,
  getCurrentUser,
  getStoredToken,
  listTickets,
  updateTicketStatus,
} from "./api";
import "./App.css";

const STREAM_API_URL = `${API_BASE_URL}/chat/stream`;
const CONVERSATIONS_API_URL = `${API_BASE_URL}/conversations`;

function createConversationId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `conversation-${Date.now()}`;
}

function createMessageId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `message-${Date.now()}-${Math.random()}`;
}

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(
    createConversationId()
  );
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [tickets, setTickets] = useState([]);
  const [isTicketsLoading, setIsTicketsLoading] = useState(false);

  useEffect(() => {
    restoreSession();
  }, []);

  useEffect(() => {
    if (currentUser) {
      loadConversationList();
      loadTickets();
    }
  }, [currentUser]);

  async function restoreSession() {
    const token = getStoredToken();

    if (!token) {
      setIsAuthLoading(false);
      return;
    }

    try {
      const user = await getCurrentUser(token);
      setCurrentUser(user);
    } catch {
      clearToken();
      setCurrentUser(null);
    } finally {
      setIsAuthLoading(false);
    }
  }

  async function completeAuthentication(token) {
    const user = await getCurrentUser(token);

    setCurrentUser(user);
    setIsAuthLoading(false);
  }

  function logout() {
    clearToken();
    setCurrentUser(null);
    setMessages([]);
    setConversations([]);
    setTickets([]);
    setConversationId(createConversationId());
    setMessage("");
    setError("");
  }

  async function loadConversationList() {
    try {
      const response = await authenticatedFetch(
        CONVERSATIONS_API_URL
      );

      if (!response.ok) {
        throw new Error(
          `Could not load conversations: HTTP ${response.status}`
        );
      }

      const data = await response.json();
      setConversations(data);
    } catch (requestError) {
      console.error(requestError);
    }
  }


  async function loadTickets() {
    setIsTicketsLoading(true);

    try {
      const data = await listTickets();
      setTickets(data);
    } catch (requestError) {
      console.error(requestError);
    } finally {
      setIsTicketsLoading(false);
    }
  }

  async function changeTicketStatus(ticketId, status) {
    try {
      await updateTicketStatus(ticketId, status);
      await loadTickets();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not update the ticket."
      );
    }
  }

  function startNewConversation() {
    if (isLoading) {
      return;
    }

    setConversationId(createConversationId());
    setMessages([]);
    setMessage("");
    setError("");
  }

  async function openConversation(selectedConversationId) {
    if (isLoading) {
      return;
    }

    setIsHistoryLoading(true);
    setError("");

    try {
      const response = await authenticatedFetch(
        `${CONVERSATIONS_API_URL}/${encodeURIComponent(
          selectedConversationId
        )}`
      );

      if (!response.ok) {
        throw new Error(
          `Could not open conversation: HTTP ${response.status}`
        );
      }

      const data = await response.json();

      setConversationId(data.conversation_id);
      setMessages(
        data.messages.map((storedMessage) => ({
          id: createMessageId(),
          role: storedMessage.role,
          content: storedMessage.content,
        }))
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not open the conversation."
      );
    } finally {
      setIsHistoryLoading(false);
    }
  }

  async function removeConversation(
    event,
    selectedConversationId
  ) {
    event.stopPropagation();

    if (isLoading) {
      return;
    }

    const confirmed = window.confirm(
      "Delete this conversation permanently?"
    );

    if (!confirmed) {
      return;
    }

    try {
      const response = await authenticatedFetch(
        `${CONVERSATIONS_API_URL}/${encodeURIComponent(
          selectedConversationId
        )}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(
          `Could not delete conversation: HTTP ${response.status}`
        );
      }

      if (selectedConversationId === conversationId) {
        startNewConversation();
      }

      await loadConversationList();
      await loadTickets();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not delete the conversation."
      );
    }
  }

  async function sendMessage(event) {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage || isLoading) {
      return;
    }

    const assistantMessageId = createMessageId();

    setMessages((current) => [
      ...current,
      {
        id: createMessageId(),
        role: "user",
        content: trimmedMessage,
      },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
      },
    ]);

    setMessage("");
    setError("");
    setIsLoading(true);

    try {
      const response = await authenticatedFetch(STREAM_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/plain",
        },
        body: JSON.stringify({
          message: trimmedMessage,
          conversation_id: conversationId,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText || `Backend returned HTTP ${response.status}`
        );
      }

      if (!response.body) {
        throw new Error(
          "The browser did not receive a response stream."
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let fullResponse = "";

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        const token = decoder.decode(value, { stream: true });
        fullResponse += token;

        setMessages((current) =>
          current.map((chatMessage) =>
            chatMessage.id === assistantMessageId
              ? { ...chatMessage, content: fullResponse }
              : chatMessage
          )
        );
      }

      const finalCharacters = decoder.decode();

      if (finalCharacters) {
        fullResponse += finalCharacters;

        setMessages((current) =>
          current.map((chatMessage) =>
            chatMessage.id === assistantMessageId
              ? { ...chatMessage, content: fullResponse }
              : chatMessage
          )
        );
      }

      await loadConversationList();
      await loadTickets();
    } catch (requestError) {
      const errorMessage =
        requestError instanceof Error
          ? requestError.message
          : "An unexpected error occurred.";

      setError(errorMessage);

      setMessages((current) =>
        current.map((chatMessage) =>
          chatMessage.id === assistantMessageId
            ? {
                ...chatMessage,
                content:
                  "The assistant could not complete this request.",
                isError: true,
              }
            : chatMessage
        )
      );
    } finally {
      setIsLoading(false);
    }
  }

  if (isAuthLoading) {
    return (
      <main className="auth-page">
        <p>Restoring session…</p>
      </main>
    );
  }

  if (!currentUser) {
    return (
      <AuthScreen onAuthenticated={completeAuthentication} />
    );
  }

  return (
    <main className="page-shell">
      <aside className="conversation-sidebar">
        <div className="sidebar-header">
          <div>
            <p className="eyebrow">History</p>
            <h2>Conversations</h2>
          </div>

          <button
            className="new-chat-button"
            onClick={startNewConversation}
            disabled={isLoading}
            type="button"
          >
            New
          </button>
        </div>

        <div className="conversation-list">
          {conversations.length === 0 && (
            <p className="sidebar-empty">
              No saved conversations yet.
            </p>
          )}

          {conversations.map((conversation) => (
            <button
              className={`conversation-item ${
                conversation.conversation_id === conversationId
                  ? "active"
                  : ""
              }`}
              key={conversation.conversation_id}
              onClick={() =>
                openConversation(conversation.conversation_id)
              }
              type="button"
            >
              <span className="conversation-preview">
                {conversation.preview || "Untitled conversation"}
              </span>

              <span className="conversation-meta">
                {conversation.message_count} messages
              </span>

              <span
                className="delete-conversation"
                onClick={(event) =>
                  removeConversation(
                    event,
                    conversation.conversation_id
                  )
                }
                role="button"
                tabIndex="0"
              >
                Delete
              </span>
            </button>
          ))}
        </div>
      </aside>

      <section className="app-shell">
        <header className="app-header">
          <div>
            <p className="eyebrow">Portfolio project</p>
            <h1>Enterprise AI Assistant</h1>
            <p className="subtitle">
              LLM providers, RAG, tools, memory, LangGraph and MCP
            </p>
          </div>

          <div className="user-controls">
            <span>
              Signed in as{" "}
              <strong>{currentUser.display_name}</strong>
            </span>

            <button
              className="secondary-button"
              onClick={logout}
              type="button"
            >
              Sign out
            </button>
          </div>

          <label className="conversation-field">
            Conversation ID
            <input
              value={conversationId}
              readOnly
              title="Conversation IDs are generated automatically."
            />
          </label>
        </header>

        <section className="chat-panel">
          <div className="message-list">
            {isHistoryLoading && (
              <div className="empty-state">
                <p>Loading conversation…</p>
              </div>
            )}

            {!isHistoryLoading && messages.length === 0 && (
              <div className="empty-state">
                <h2>Ask the enterprise assistant</h2>
                <p>
                  Try a policy question, calculation, or IT-ticket
                  request.
                </p>
              </div>
            )}

            {messages.map((chatMessage) => (
              <article
                className={`message ${chatMessage.role} ${
                  chatMessage.isError ? "message-error" : ""
                }`}
                key={chatMessage.id}
              >
                <strong>
                  {chatMessage.role === "user"
                    ? "You"
                    : "Assistant"}
                </strong>

                <p>
                  {chatMessage.content ||
                    (isLoading ? "Thinking…" : "")}
                </p>
              </article>
            ))}
          </div>

          {error && <p className="error-message">{error}</p>}

          <form className="message-form" onSubmit={sendMessage}>
            <textarea
              value={message}
              onChange={(event) =>
                setMessage(event.target.value)
              }
              placeholder="Ask a question..."
              rows="3"
              disabled={isLoading || isHistoryLoading}
            />

            <button
              disabled={isLoading || isHistoryLoading}
              type="submit"
            >
              {isLoading ? "Responding…" : "Send"}
            </button>
          </form>
        </section>

        <section className="ticket-panel">
          <div className="ticket-header">
            <div>
              <p className="eyebrow">Persisted workflow</p>
              <h2>{currentUser.role === "support" ? "Support tickets" : "My tickets"}</h2>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={loadTickets}
              disabled={isTicketsLoading}
            >
              {isTicketsLoading ? "Refreshing…" : "Refresh"}
            </button>
          </div>

          {tickets.length === 0 ? (
            <p className="ticket-empty">No persisted tickets yet.</p>
          ) : (
            <div className="ticket-list">
              {tickets.map((ticket) => (
                <article className="ticket-card" key={ticket.ticket_id}>
                  <div>
                    <strong>{ticket.ticket_id}</strong>
                    {currentUser.role === "support" && (
                      <span className="ticket-requester">Requester: {ticket.requester_username}</span>
                    )}
                    <p>{ticket.description}</p>
                    <span className="ticket-meta">
                      Status: {ticket.status} · Created {new Date(ticket.created_at).toLocaleString()}
                    </span>
                  </div>

                  {currentUser.role === "support" && ticket.status !== "resolved" && (
                    <div className="ticket-actions">
                      {ticket.status === "created" && (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => changeTicketStatus(ticket.ticket_id, "in_progress")}
                        >
                          Start work
                        </button>
                      )}
                      {ticket.status === "in_progress" && (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => changeTicketStatus(ticket.ticket_id, "resolved")}
                        >
                          Resolve
                        </button>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

export default App;