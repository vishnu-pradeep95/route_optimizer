/**
 * Entry point for the Kerala LPG Delivery Ops Dashboard.
 *
 * Font imports: DM Sans (headings, UI text) + IBM Plex Mono (data, numbers).
 * Why @fontsource instead of Google Fonts CDN?
 * - Self-hosted = no GDPR cookie banner issues, no external requests
 * - Guaranteed availability (no CDN dependency)
 * - Tree-shakeable — only the weights we import get bundled
 * See: https://fontsource.org/docs/getting-started/introduction
 *
 * Why we import maplibre-gl CSS here instead of in RouteMap:
 * The CSS must be loaded once globally before any MapLibre component renders.
 * Importing in the entry point guarantees it's available app-wide.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// ── Fonts ────────────────────────────────────────────────────────────
// DM Sans: geometric sans-serif for headings and UI text
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-sans/700.css'

// IBM Plex Mono: technical monospace for data, numbers, and metrics
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'

// MapLibre GL CSS — must be imported before any map component mounts
import 'maplibre-gl/dist/maplibre-gl.css'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
