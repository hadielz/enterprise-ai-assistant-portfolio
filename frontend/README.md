# Enterprise AI Assistant Frontend

React/Vite frontend for the Enterprise AI Assistant reference application.

## Current responsibilities

- register and sign in users;
- store the current bearer token in browser `sessionStorage`;
- restore the authenticated session through `/api/auth/me`;
- stream assistant responses from `/api/chat/stream`;
- list, reopen, create, and delete user-owned conversations;
- list the authenticated user's tickets and expose support-only status transitions when the current user has the `support` role;
- provide the current responsive reference UI.

## Development

Install dependencies:

```bash
npm ci
```

Start the Vite development server:

```bash
npm run dev
```

Create the production bundle:

```bash
npm run build
```

Run ESLint:

```bash
npm run lint
```

## API configuration

`src/api.js` resolves the backend API location in this order:

1. runtime `window.__APP_CONFIG__.apiBaseUrl`;
2. build-time `VITE_API_BASE_URL`;
3. local fallback `http://localhost:8000/api`.

The production nginx container writes `runtime-config.js` at startup from the
`API_BASE_URL` environment variable, so the same frontend image can target the
deployed backend without being rebuilt.
