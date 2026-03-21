import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { AppProvider } from './src/context/AppContext';
import LiveRecordingScreen from './src/screens/LiveRecordingScreen';
import AnalysisScreen from './src/screens/AnalysisScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <AppProvider>
      <NavigationContainer>
        <Stack.Navigator
          initialRouteName="LiveRecordingScreen"
          screenOptions={{
            headerShown: false,
          }}
        >
          <Stack.Screen name="LiveRecordingScreen" component={LiveRecordingScreen} />
          <Stack.Screen name="AnalysisScreen" component={AnalysisScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </AppProvider>
  );
}
