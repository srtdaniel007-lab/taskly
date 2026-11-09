# TaskPulse / Trackly - Frontend

A lightweight, responsive Single Page Application (SPA) dashboard built with **Tailwind CSS**, **Alpine.js**, and **Lucide Icons**.

## Local Development

Simply serve the `frontend` folder using any static HTTP server:

```bash
# Using Python:
python -m http.server 3000

# Using Node / npx:
npx serve .
```

Then visit `http://localhost:3000`.

## Connecting to Backend

1. **Via `config.js`**:
   Edit `config.js` and set:
   ```javascript
   window.__ENV__ = {
     API_BASE_URL: "https://taskpulse-backend.onrender.com" // or http://localhost:8000
   };
   ```

2. **Via Browser UI**:
   Click the **API Status** pill in the top header and enter your backend URL directly. The setting will be saved in your browser's `localStorage`.

## Deployment on Render

This frontend is configured as a Render **Static Site** in `../render.yaml`:
- **Runtime**: `static`
- **Root Directory**: `frontend`
- **Publish Path**: `.`
- **Routes**: Rewrites all `/*` paths to `/index.html`

