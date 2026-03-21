import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, spacing, borderRadius } from '../theme';

/**
 * AnalysisCard — displays one insight from the backend.
 *
 * Accepts backend snake_case fields directly:
 *   speaker_label, transcript, sound_type, loudness_label,
 *   loudness_db, distance_label, timestamp_ms
 *
 * Also accepts the legacy camelCase shape from VoiceSession's mapper:
 *   speaker, speech, soundType, loudness, distance
 */
const AnalysisCard = ({ insight }) => {
  // Support both backend snake_case and mapped camelCase
  const speaker   = insight.speaker_label  || insight.speaker   || 'Unknown';
  const speech    = insight.transcript     || insight.speech     || null;
  const soundType = (insight.sound_type    || insight.soundType  || 'unknown').toLowerCase();
  const loudness  = insight.loudness_label || insight.loudness   || 'unknown';
  const loudnessDb = insight.loudness_db != null
    ? `${Number(insight.loudness_db).toFixed(1)} dB`
    : null;
  const distance  = insight.distance_label || insight.distance  || 'unknown';
  const ts        = insight.timestamp_ms   ?? insight.timestamp ?? null;
  const time      = ts != null ? `${(ts / 1000).toFixed(1)}s` : null;

  const getBadgeColor = () => {
    switch (soundType) {
      case 'speech': return colors.badge?.speech  || colors.primary;
      case 'music':  return colors.badge?.music   || colors.purple || '#7c3aed';
      case 'noise':  return colors.badge?.noise   || colors.orange || '#f97316';
      default:       return colors.badge?.default || colors.gray;
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.speaker}>{speaker}</Text>
          {time && <Text style={styles.time}>{time}</Text>}
        </View>
        <View style={[styles.badge, { backgroundColor: getBadgeColor() }]}>
          <Text style={styles.badgeText}>{soundType}</Text>
        </View>
      </View>

      {speech ? (
        <Text style={styles.transcript}>"{speech}"</Text>
      ) : (
        <Text style={styles.noTranscript}>No transcript</Text>
      )}

      <View style={styles.details}>
        <View style={styles.detailItem}>
          <Text style={styles.detailLabel}>Distance</Text>
          <Text style={styles.detailValue}>{distance}</Text>
        </View>
        <View style={styles.detailItem}>
          <Text style={styles.detailLabel}>Loudness</Text>
          <Text style={styles.detailValue}>{loudnessDb || loudness}</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.card.light,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  headerLeft: { flex: 1 },
  speaker: { fontSize: 15, fontWeight: '600', color: colors.text.dark },
  time:    { fontSize: 11, color: colors.gray, marginTop: 2 },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: 10,
    marginLeft: spacing.sm,
  },
  badgeText: { color: colors.text.light, fontSize: 11, textTransform: 'capitalize' },
  transcript:   { fontSize: 14, color: colors.text.dark, marginBottom: spacing.sm, fontStyle: 'italic', lineHeight: 20 },
  noTranscript: { fontSize: 13, color: colors.gray, marginBottom: spacing.sm },
  details: { flexDirection: 'row', gap: spacing.lg },
  detailItem: {},
  detailLabel: { fontSize: 11, color: colors.gray, marginBottom: 2 },
  detailValue: { fontSize: 13, color: colors.text.dark, textTransform: 'capitalize' },
});

export default AnalysisCard;
