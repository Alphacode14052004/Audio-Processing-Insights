# Type Definitions and Enums

## Insight Object Shape

```javascript
{
  speech: string,       // Transcript text
  speaker: string,      // Speaker label (e.g., "Speaker 1")
  soundType: string,    // Audio type: "speech", "music", "noise"
  distance: string,     // Distance: "near", "far"
  loudness: string,     // Volume level: "loud", "moderate", "quiet"
  timestamp: number     // Unix timestamp in milliseconds
}
```

## Enums

### AppStatus
```javascript
APP_STATUS = {
  IDLE: 'idle',        // Initial state, no recording
  RECORDING: 'recording',  // Actively recording
  ANALYZING: 'analyzing',  // Processing after recording stops
  DONE: 'done'         // Analysis complete
}
```

### SoundType
```javascript
SOUND_TYPES = ['speech', 'music', 'noise']
```

### Speaker
```javascript
SPEAKERS = ['Speaker 1', 'Speaker 2', 'Speaker 3']
```

### Distance
```javascript
DISTANCES = ['near', 'far']
```

### Loudness
```javascript
LOUDNESS_LEVELS = ['loud', 'moderate', 'quiet']
```

## Score Mappings (for Radar Chart)

### Loudness → Score
| Value     | Score |
|-----------|-------|
| loud      | 90    |
| moderate  | 55    |
| quiet     | 20    |

### Distance → Score
| Value     | Score |
|-----------|-------|
| near      | 80    |
| far       | 30    |

### SoundType → Score (Activity axis)
| Value     | Score |
|-----------|-------|
| speech    | 85    |
| music     | 70    |
| noise     | 40    |

### Fixed Values
| Metric    | Score |
|-----------|-------|
| Confidence | 65    |
| Clarity   | 75    |

## Badge Colors

| Sound Type | Hex Color |
|------------|-----------|
| speech     | #4A90E2   |
| music      | #9B59B6   |
| noise      | #E67E22   |
| default    | #95A5A6   |

## Radar Chart Axes

1. Loudness
2. Distance
3. Confidence (fixed: 65)
4. Clarity (fixed: 75)
5. Activity (derived from soundType)

## VoiceSession Interface

```javascript
class VoiceSession {
  start()           // Start recording/connection
  stop()             // Stop recording/connection
  onData(callback)  // Register callback for incoming data
  isRecording()     // Returns boolean
  destroy()          // Cleanup resources
}
```
