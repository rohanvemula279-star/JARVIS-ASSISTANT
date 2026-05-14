import { useState, useEffect, useCallback, useRef } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { micService } from '../services/speech/micService';

export const useVoiceControls = () => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isAvailable, setIsAvailable] = useState(false);
  
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setIsAvailable(!!SpeechRecognition);
  }, []);
  
  const startVoice = useCallback(() => {
    if (!isAvailable) {
      console.warn('Speech recognition not available');
      return;
    }
    micService.startListening();
    setIsListening(true);
  }, [isAvailable]);
  
  const stopVoice = useCallback(() => {
    micService.stopListening();
    setIsListening(false);
  }, []);
  
  const toggleVoice = useCallback(() => {
    if (isListening) {
      stopVoice();
    } else {
      startVoice();
    }
  }, [isListening, startVoice, stopVoice]);
  
  return {
    isListening,
    isAvailable,
    transcript,
    startVoice,
    stopVoice,
    toggleVoice
  };
};