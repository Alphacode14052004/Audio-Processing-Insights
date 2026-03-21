import React, { createContext, useContext, useState, useCallback } from 'react';

const AppContext = createContext(null);

export const APP_STATUS = {
  IDLE: 'idle',
  RECORDING: 'recording',
  ANALYZING: 'analyzing',
  DONE: 'done',
};

export const AppProvider = ({ children }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [liveInsights, setLiveInsights] = useState([]);
  const [analysisResults, setAnalysisResults] = useState([]);
  const [appStatus, setAppStatus] = useState(APP_STATUS.IDLE);

  const startRecording = useCallback(() => {
    setIsRecording(true);
    setAppStatus(APP_STATUS.RECORDING);
    setLiveInsights([]);
  }, []);

  const stopRecording = useCallback(() => {
    setIsRecording(false);
  }, []);

  const addInsight = useCallback((insight) => {
    setLiveInsights((prev) => {
      const updated = [insight, ...prev];
      return updated.slice(0, 10);
    });
  }, []);

  const startAnalyzing = useCallback(() => {
    setAppStatus(APP_STATUS.ANALYZING);
  }, []);

  const finishAnalysis = useCallback((results) => {
    setAnalysisResults(results);
    setAppStatus(APP_STATUS.DONE);
  }, []);

  const resetState = useCallback(() => {
    setIsRecording(false);
    setLiveInsights([]);
    setAnalysisResults([]);
    setAppStatus(APP_STATUS.IDLE);
  }, []);

  const value = {
    isRecording,
    liveInsights,
    analysisResults,
    appStatus,
    startRecording,
    stopRecording,
    addInsight,
    startAnalyzing,
    finishAnalysis,
    resetState,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
