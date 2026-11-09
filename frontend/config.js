/**
 * TaskPulse Frontend - Runtime Configuration
 *
 * In local development:
 *   Leave API_BASE_URL as "" (empty string) to make requests to the same origin.
 *
 * In production on Render (or other platforms):
 *   Set API_BASE_URL to your deployed Backend Web Service URL:
 *   e.g. API_BASE_URL: "https://taskpulse-backend.onrender.com"
 *
 * Note: You can also configure the backend URL directly in the app UI,
 * which will persist to your browser's localStorage.
 */
window.__ENV__ = {
  API_BASE_URL: "https://taskly-zk8p.onrender.com"
};

