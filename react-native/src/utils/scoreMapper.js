export const mapLoudnessToScore = (loudness) => {
  const mapping = {
    loud: 90,
    moderate: 55,
    quiet: 20,
  };
  return mapping[loudness.toLowerCase()] || 50;
};

export const mapDistanceToScore = (distance) => {
  const mapping = {
    near: 80,
    far: 30,
  };
  return mapping[distance.toLowerCase()] || 50;
};

export const mapSoundTypeToScore = (soundType) => {
  const mapping = {
    speech: 85,
    music: 70,
    noise: 40,
  };
  return mapping[soundType.toLowerCase()] || 50;
};

export const mapInsightToRadarData = (insight) => {
  return [
    {
      Loudness: mapLoudnessToScore(insight.loudness),
      Distance: mapDistanceToScore(insight.distance),
      Confidence: 65,
      Clarity: 75,
      Activity: mapSoundTypeToScore(insight.soundType),
    },
  ];
};

export const RADAR_LABELS = ['Loudness', 'Distance', 'Confidence', 'Clarity', 'Activity'];
