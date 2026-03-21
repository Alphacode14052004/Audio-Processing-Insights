import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { colors, spacing, borderRadius } from '../theme';
import AnalysisCard from '../components/AnalysisCard';

const AnalysisScreen = ({ navigation, route }) => {
  // Full session object from backend (via VoiceSession.onComplete)
  const session = route.params?.session || null;

  // Extract speakers and speech-only insights from session
  const speakers = session?.speakers || [];
  const allInsights = session?.insights || [];
  // Show all insights that have a speaker label (speech chunks)
  const speechInsights = allInsights.filter(
    (i) => i.speaker_label && i.sound_type === 'speech'
  );

  const handleRecordAgain = () => {
    navigation.navigate('LiveRecordingScreen');
  };

  // Format loudness_db nicely
  const fmtDb = (db) => (db != null ? `${db.toFixed(1)} dB` : 'N/A');

  return (
    <View style={styles.container}>
      {/* ── Header ── */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Analysis</Text>
      </View>

      {/* ── Session summary ── */}
      <View style={styles.summaryBar}>
        <Text style={styles.summaryText}>
          {session
            ? `${session.total_insights} insights · ${speakers.length} speaker${speakers.length !== 1 ? 's' : ''} · ${Math.round(session.duration_seconds)}s`
            : 'No session data'}
        </Text>
      </View>

      <ScrollView
        style={styles.content}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Speaker summary cards ── */}
        {speakers.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Speakers</Text>
            {speakers.map((spk) => (
              <View key={spk.id} style={styles.speakerCard}>
                <View style={styles.speakerRow}>
                  <Text style={styles.speakerName}>{spk.speaker_label}</Text>
                  <Text style={styles.speakerWords}>{spk.word_count} words</Text>
                </View>
                <View style={styles.speakerRow}>
                  <Text style={styles.speakerMeta}>
                    Avg {fmtDb(spk.avg_loudness_db)} · {spk.turn_count} turn{spk.turn_count !== 1 ? 's' : ''}
                  </Text>
                  <Text style={styles.speakerMeta}>
                    {(spk.total_speaking_ms / 1000).toFixed(1)}s speaking
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* ── Per-chunk analysis cards ── */}
        {speechInsights.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Transcript</Text>
            {speechInsights.map((insight, index) => (
              <AnalysisCard
                key={insight.id || `${insight.timestamp_ms}-${index}`}
                insight={insight}
              />
            ))}
          </View>
        )}

        {speechInsights.length === 0 && session && (
          <Text style={styles.emptyText}>No speech detected in this session.</Text>
        )}
        {!session && (
          <Text style={styles.emptyText}>
            Session data unavailable. Check your backend connection.
          </Text>
        )}
      </ScrollView>

      {/* ── Footer ── */}
      <View style={styles.footer}>
        <TouchableOpacity style={styles.recordAgainButton} onPress={handleRecordAgain}>
          <Text style={styles.recordAgainText}>Record Again</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background.light },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    paddingTop: spacing.xl,
    backgroundColor: colors.card.light,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.light,
  },
  backButton: { padding: spacing.sm, marginRight: spacing.sm },
  backArrow:  { fontSize: 24, color: colors.text.dark },
  title:      { fontSize: 20, fontWeight: '600', color: colors.text.dark },

  summaryBar: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.card.light,
  },
  summaryText: { fontSize: 13, color: colors.gray },

  content:       { flex: 1 },
  scrollContent: { padding: spacing.md, paddingBottom: spacing.lg },

  section:      { marginBottom: spacing.lg },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.gray,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: spacing.sm,
  },

  speakerCard: {
    backgroundColor: colors.card.light,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
  speakerRow:  { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 2 },
  speakerName: { fontSize: 16, fontWeight: '600', color: colors.text.dark },
  speakerWords: { fontSize: 14, color: colors.primary, fontWeight: '500' },
  speakerMeta: { fontSize: 12, color: colors.gray },

  emptyText: { color: colors.gray, textAlign: 'center', marginTop: spacing.xl, fontSize: 14 },

  footer: {
    padding: spacing.md,
    backgroundColor: colors.card.light,
    borderTopWidth: 1,
    borderTopColor: colors.border.light,
  },
  recordAgainButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  recordAgainText: { color: colors.text.light, fontSize: 16, fontWeight: '600' },
});

export default AnalysisScreen;
