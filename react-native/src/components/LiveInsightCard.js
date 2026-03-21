import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, spacing, borderRadius } from '../theme';

const LiveInsightCard = ({ insight }) => {
  const getAccentColor = () => {
    const soundType = (insight.soundType || '').toLowerCase();
    switch (soundType) {
      case 'speech':
        return colors.primary;
      case 'music':
        return colors.purple;
      case 'noise':
        return colors.orange;
      default:
        return colors.gray;
    }
  };

  const formatLoudness = () => {
    if (insight.loudness_db !== undefined) {
      return `${insight.loudness_db} dB`;
    }
    return insight.loudness || 'N/A';
  };

  const formatDistance = () => {
    if (insight.distance_cm !== undefined) {
      return `${insight.distance_cm} cm`;
    }
    return insight.distance || 'N/A';
  };

  return (
    <View style={[styles.container, { borderLeftColor: getAccentColor() }]}>
      <View style={styles.header}>
        <Text style={styles.speaker}>{insight.speaker || 'Unknown'}</Text>
        <View style={[styles.badge, { backgroundColor: getAccentColor() }]}>
          <Text style={styles.badgeText}>{insight.soundType || 'audio'}</Text>
        </View>
      </View>
      <Text style={styles.speech}>{insight.speech || 'Processing audio...'}</Text>
      <View style={styles.details}>
        <View style={styles.detailItem}>
          <Text style={styles.detailLabel}>Distance:</Text>
          <Text style={styles.detailValue}>{formatDistance()}</Text>
        </View>
        <View style={styles.detailItem}>
          <Text style={styles.detailLabel}>Loudness:</Text>
          <Text style={styles.detailValue}>{formatLoudness()}</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.card.dark,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderLeftWidth: 4,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  speaker: {
    color: colors.text.light,
    fontSize: 14,
    fontWeight: '600',
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: 12,
  },
  badgeText: {
    color: colors.text.light,
    fontSize: 12,
    textTransform: 'capitalize',
  },
  speech: {
    color: colors.text.light,
    fontSize: 16,
    marginBottom: spacing.sm,
  },
  details: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  detailItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  detailLabel: {
    color: colors.gray,
    fontSize: 12,
    marginRight: spacing.xs,
  },
  detailValue: {
    color: colors.text.light,
    fontSize: 12,
    textTransform: 'capitalize',
  },
});

export default LiveInsightCard;
