/**
 * Backend API Configuration
 *
 * Expo Go on a real Android device connects over your local WiFi.
 * Set BACKEND_IP to your computer's LAN IP (find it with `ipconfig` on Windows).
 *
 * Example: '192.168.1.42'
 *
 * For Android emulator use: '10.0.2.2'
 * For iOS simulator use:    'localhost'
 */
export const BACKEND_IP = '172.31.98.120'; // ← CHANGE THIS to your computer's IP
export const BACKEND_PORT = 8000;

export const BASE_HTTP = `http://${BACKEND_IP}:${BACKEND_PORT}`;
export const BASE_WS = `ws://${BACKEND_IP}:${BACKEND_PORT}`;
