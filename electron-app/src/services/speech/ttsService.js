import { useAssistantStore } from '../../state/assistantStore';

export const ttsService = {
  speak: (text) => {
    if (!('speechSynthesis' in window)) return;
    const { ttsEnabled, muted } = useAssistantStore.getState();
    if (!ttsEnabled || muted) return;

    window.speechSynthesis.cancel(); // stop current
    const ut = new SpeechSynthesisUtterance(text);
    
    // Look for female voices (Zira, Google US Female, etc.)
    const voices = window.speechSynthesis.getVoices();
    const femaleVoice = voices.find(v => 
      v.name.includes('Zira') || 
      v.name.includes('Female') || 
      (v.name.includes('Google') && v.lang.includes('en'))
    );
    if (femaleVoice) ut.voice = femaleVoice;
    
    ut.pitch = 1.0;
    ut.rate = 1.0;
    window.speechSynthesis.speak(ut);
  },
  stop: () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  }
};
