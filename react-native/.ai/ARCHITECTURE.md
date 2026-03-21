# Architecture Overview

## File Structure

```
├── App.js                          # Main entry point with navigation setup
├── app.json                        # Expo configuration
├── package.json                    # Dependencies and scripts
├── babel.config.js                 # Babel configuration
├── src/
│   ├── theme.js                    # Centralized color/spacing constants
│   ├── context/
│   │   └── AppContext.js           # React Context for state management
│   ├── sessions/
│   │   └── VoiceSession.js         # Mock WebSocket class (swappable)
│   ├── utils/
│   │   └── scoreMapper.js          # String-to-number mapping for radar charts
│   ├── components/
│   │   ├── LiveInsightCard.js      # Live streaming insight card
│   │   ├── AnalysisCard.js         # Analysis results card
│   │   └── RadarChart.js           # Wrapper for react-native-chart-kit RadarChart
│   └── screens/
│       ├── LiveRecordingScreen.js  # Recording UI with mock WebSocket
│       └── AnalysisScreen.js       # Analysis results display
└── .ai/
    ├── ARCHITECTURE.md             # This file
    └── TYPES.md                    # Type definitions and enums
```

## Architecture Summary

- **App.js**: Root component wrapping the app with AppProvider and NavigationContainer
- **theme.js**: All color constants, spacing values, and border radii in one place
- **AppContext.js**: Global state management with React Context (isRecording, liveInsights, analysisResults, appStatus)
- **VoiceSession.js**: Abstract class for WebSocket/mock - swap implementation here only
- **scoreMapper.js**: Utility to convert insight string values to radar chart numeric scores
- **LiveInsightCard.js**: Displays streaming insights during recording
- **AnalysisCard.js**: Displays analyzed insight with radar chart visualization
- **RadarChart.js**: Wraps react-native-chart-kit RadarChart with consistent styling
- **LiveRecordingScreen.js**: Main recording screen with pulse animation and mock data stream
- **AnalysisScreen.js**: Results screen with scrollable cards and "Record Again" button
