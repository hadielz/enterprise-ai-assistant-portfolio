import { useState } from "react";
import {
  loginUser,
  registerUser,
  storeToken,
} from "./api";

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();

    setError("");
    setIsSubmitting(true);

    try {
      if (mode === "register") {
        await registerUser({
          username,
          displayName,
          password,
        });
      }

      const tokenData = await loginUser(username, password);

      storeToken(tokenData.access_token);
      await onAuthenticated(tokenData.access_token);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Authentication failed."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <p className="eyebrow">Enterprise AI Assistant</p>
        <h1>
          {mode === "login" ? "Welcome back" : "Create account"}
        </h1>

        <p className="subtitle">
          Sign in to access your private conversations and assistant.
        </p>

        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label>
              Display name
              <input
                value={displayName}
                onChange={(event) =>
                  setDisplayName(event.target.value)
                }
                required
              />
            </label>
          )}

          <label>
            Username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={
                mode === "login"
                  ? "current-password"
                  : "new-password"
              }
              minLength="8"
              required
            />
          </label>

          {error && <p className="error-message">{error}</p>}

          <button disabled={isSubmitting} type="submit">
            {isSubmitting
              ? "Please wait…"
              : mode === "login"
                ? "Sign in"
                : "Register"}
          </button>
        </form>

        <button
          className="auth-mode-button"
          onClick={() =>
            setMode((current) =>
              current === "login" ? "register" : "login"
            )
          }
          type="button"
        >
          {mode === "login"
            ? "Need an account? Register"
            : "Already registered? Sign in"}
        </button>
      </section>
    </main>
  );
}

export default AuthScreen;