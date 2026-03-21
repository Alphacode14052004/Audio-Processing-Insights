import React, { useRef, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Animated,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { useAppContext, APP_STATUS } from '../context/AppContext';
import { colors, spacing } from '../theme';
import VoiceSession from '../sessions/VoiceSession';
import LiveInsightCard from '../components/LiveInsightCard';

const LiveRecordingScreen = ({ navigation }) => {
  const {
    isRecording,
    liveInsights,
    appStatus,
    startRecording,
    stopRecording,
    addInsight,
    startAnalyzing,
    finishAnalysis,
    resetState,
  } = useAppContext();

  const voiceSessionRef = useRef(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    return () => {
      if (voiceSessionRef.current) {
        voiceSessionRef.current.destroy();
      }
    };
  }, []);

  const startPulseAnimation = useCallback(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.15,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, [pulseAnim]);

  const stopPulseAnimation = useCallback(() => {
    pulseAnim.stopAnimation();
    pulseAnim.setValue(1);
  }, [pulseAnim]);

  const handleStartRecording = useCallback(() => {
    voiceSessionRef.current = new VoiceSession();

    // Each live chunk → push to UI
    voiceSessionRef.current.onData((insight) => {
      addInsight(insight);
    });

    // When backend finishes and returns the full session → navigate
    voiceSessionRef.current.onComplete((session) => {
      finishAnalysis(session);
      navigation.navigate('AnalysisScreen', { session });
    });

    voiceSessionRef.current.start();
    startRecording();
    startPulseAnimation();
  }, [addInsight, startRecording, startPulseAnimation, finishAnalysis, navigation]);

  const handleStopRecording = useCallback(() => {
    if (voiceSessionRef.current) {
      voiceSessionRef.current.stop();
    }
    stopRecording();
    stopPulseAnimation();
    startAnalyzing();
    // Navigation happens via onComplete callback once backend returns session_complete
  }, [stopRecording, stopPulseAnimation, startAnalyzing]);

  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      if (appStatus === APP_STATUS.IDLE) {
        resetState();
      }
    });
    return unsubscribe;
  }, [navigation, appStatus, resetState]);

  const isAnalyzing = appStatus === APP_STATUS.ANALYZING;

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <View style={styles.liveFeed}>
          {isRecording ? (
            <ScrollView
              style={styles.scrollView}
              contentContainerStyle={styles.scrollContent}
              showsVerticalScrollIndicator={false}
            >
              {liveInsights.map((insight, index) => (
                <LiveInsightCard key={`${insight.timestamp}-${index}`} insight={insight} />
              ))}
            </ScrollView>
          ) : (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>Press Start to begin recording</Text>
            </View>
          )}
        </View>

        <View style={styles.controls}>
          <TouchableOpacity
            style={[
              styles.recordButton,
              { backgroundColor: isRecording ? colors.danger : colors.primary },
            ]}
            onPress={isRecording ? handleStopRecording : handleStartRecording}
            disabled={isAnalyzing}
          >
            <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
              <Text style={styles.recordIcon}>{isRecording ? '■' : '●'}</Text>
            </Animated.View>
            <Text style={styles.recordLabel}>
              {isAnalyzing ? 'Processing...' : isRecording ? 'Stop' : 'Start Recording'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <Modal visible={isAnalyzing} animationType="fade" transparent>
        <View style={styles.overlay}>
          <View style={styles.overlayContent}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.overlayText}>Analyzing...</Text>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.dark,
  },
  content: {
    flex: 1,
    padding: spacing.md,
  },
  liveFeed: {
    flex: 1,
    marginBottom: spacing.lg,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: spacing.md,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    color: colors.gray,
    fontSize: 16,
  },
  controls: {
    alignItems: 'center',
    paddingBottom: spacing.xl,
  },
  recordButton: {
    width: 160,
    height: 160,
    borderRadius: 80,
    justifyContent: 'center',
    alignItems: 'center',
    flexDirection: 'column',
  },
  recordIcon: {
    color: colors.text.light,
    fontSize: 40,
    marginBottom: spacing.sm,
  },
  recordLabel: {
    color: colors.text.light,
    fontSize: 16,
    fontWeight: '600',
  },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  overlayContent: {
    alignItems: 'center',
  },
  overlayText: {
    color: colors.text.light,
    fontSize: 20,
    marginTop: spacing.md,
  },
});

export default LiveRecordingScreen;
