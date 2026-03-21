import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme';
import { RADAR_LABELS } from '../utils/scoreMapper';

const InsightRadarChart = ({ data, size = 120 }) => {
  if (!data || data.length === 0) {
    return null;
  }

  const radarData = data[0];
  
  return (
    <View style={styles.container}>
      <View style={styles.grid}>
        {RADAR_LABELS.map((label, index) => (
          <View key={index} style={styles.item}>
            <Text style={styles.label}>{label}</Text>
            <View style={styles.barContainer}>
              <View 
                style={[
                  styles.bar, 
                  { 
                    width: `${Math.max(0, Math.min(100, radarData[label] || 0))}%`,
                    backgroundColor: colors.primary
                  }
                ]} 
              />
            </View>
            <Text style={styles.value}>{radarData[label] || 0}</Text>
          </View>
        ))}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: 120,
  },
  grid: {
    gap: 2,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  label: {
    fontSize: 9,
    color: '#666',
    width: 35,
  },
  barContainer: {
    flex: 1,
    height: 8,
    backgroundColor: '#f0f0f0',
    borderRadius: 2,
    overflow: 'hidden',
  },
  bar: {
    height: '100%',
    borderRadius: 2,
  },
  value: {
    fontSize: 9,
    color: '#666',
    width: 20,
    textAlign: 'right',
  },
});

export default InsightRadarChart;