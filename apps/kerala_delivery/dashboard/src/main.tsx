/**
 * Entry point for the Kerala LPG Delivery Ops Dashboard.
 *
 * Why we import maplibre-gl CSS here instead of in RouteMap:
 * The CSS must be loaded once globally before any MapLibre component renders.
 * Importing in the entry point guarantees it's available app-wide.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// MapLibre GL CSS — must be imported before any map component mounts
import 'maplibre-gl/dist/maplibre-gl.css'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
