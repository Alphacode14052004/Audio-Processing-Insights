# Agent Guidelines for Voice Insights App

This document provides guidelines for agents working on this codebase.

## Project Overview

This is an **Expo/React Native** mobile application for voice recording and analysis. The app records audio, displays live insights during recording, and shows analysis results with radar charts.

## Build Commands

```bash
# Start development server (Metro bundler)
npm start

# Run on Android
npm run android

# Run on iOS
npm run ios

# Run on web
npm run web
```

Note: This project does not currently have dedicated lint or test scripts. For Expo projects, you can add:

```bash
# Add ESLint
npm install --save-dev eslint

# Add Jest
npm install --save-dev jest @testing-library/react-native
```

## Code Style Guidelines

### General Conventions

- **Language**: JavaScript (no TypeScript)
- **Framework**: React with hooks (useState, useEffect, useCallback, useRef)
- **Styling**: StyleSheet API (no CSS-in-JS libraries)
- **Navigation**: React Navigation v7 (native-stack)

### Naming Conventions

- **Components**: PascalCase (e.g., `LiveRecordingScreen`, `AnalysisCard`)
- **Variables/Functions**: camelCase (e.g., `handleStartRecording`, `liveInsights`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `APP_STATUS`, `RADAR_LABELS`)
- **File names**: PascalCase for components, camelCase for utilities (e.g., `scoreMapper.js`)

### Imports Organization

Order imports as follows:

1. React core (e.g., `import React, { useState, useEffect } from 'react'`)
2. Library imports (e.g., `import { View, Text } from 'react-native'`)
3. Navigation imports (e.g., `import { useAppContext } from '../context/AppContext'`)
4. Relative local imports (e.g., `import { colors, spacing } from '../theme'`)

Example:
```javascript
import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppContext, APP_STATUS } from '../context/AppContext';
import { colors, spacing } from '../theme';
import LiveInsightCard from '../components/LiveInsightCard';
```

### Component Structure

Use functional components with hooks. Structure as:

1. Component definition with props destructuring
2. State/Context hooks
3. Refs (useRef)
4. Callbacks (useCallback)
5. Effects (useEffect)
6. Render logic
7. StyleSheet at bottom
8. Export default

### State Management

- Use React Context (`AppContext.js`) for global state
- Use local useState for component-specific state
- Wrap state updates in useCallback for stable references

### Error Handling

- Check context existence in custom hooks (see `useAppContext`)
- Use default cases in switch statements for unhandled values

### File Structure

```
src/
├── components/     # Reusable UI components
├── context/       # React Context providers
├── screens/       # Screen-level components
├── sessions/      # Data session handlers (WebSocket/mock)
├── utils/         # Utility functions
└── theme.js       # Design tokens (colors, spacing, etc.)
```

### Theme Constants

All colors, spacing values, and border radii are centralized in `src/theme.js`. Use these constants instead of hardcoded values.

### Constants and Enums

Reference `.ai/TYPES.md` for type definitions, enums, and score mappings.

### Radar Chart Data

The radar chart uses 5 axes: Loudness, Distance, Confidence (fixed: 65), Clarity (fixed: 75), Activity (derived from soundType). See `scoreMapper.js` for the mapping logic.

## Key Files

| File | Purpose |
|------|---------|
| `App.js` | Root component with navigation setup |
| `src/context/AppContext.js` | Global state management |
| `src/theme.js` | Design tokens |
| `src/screens/LiveRecordingScreen.js` | Main recording UI |
| `src/screens/AnalysisScreen.js` | Results display |
| `src/utils/scoreMapper.js` | Convert string values to chart scores |

## Development Notes

- The app uses mock WebSocket (`VoiceSession.js`) - swap this for real implementation
- Radar charts use `react-native-chart-kit`
- Navigation uses React Navigation v7 native-stack
- The app records audio via expo-av plugin