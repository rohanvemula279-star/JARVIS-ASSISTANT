import { useAssistantStore } from '../../state/assistantStore';

class MicService {
  constructor() {
    this.recognition = null;
    this.isAvailable = false;
    this.isListening = false;

    // Use Chrome's built-in Speech Recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
      this.isAvailable = true;
      this.recognition = new SpeechRecognition();

      // Configure for best accuracy
      this.recognition.continuous = false; // Single detection is more accurate
      this.recognition.interimResults = true;
      this.recognition.maxAlternatives = 3; // Get multiple interpretations
      this.recognition.lang = 'en-US'; // Default to English

      this.recognition.onresult = (event) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const result = event.results[i];
          if (result.isFinal) {
            // Get the most confident transcription
            final += result[0].transcript;
            console.log("Voice detected:", final, "confidence:", result[0].confidence);
          } else {
            interim += result[0].transcript;
          }
        }

        useAssistantStore.getState().setTranscript(interim, final);

        if (final && window.assistant) {
          const cleanMessage = final.trim();
          if (cleanMessage.length > 0) {
            useAssistantStore.getState().addMessage({
              id: Date.now().toString(),
              role: 'user',
              content: cleanMessage,
              createdAt: new Date().toISOString()
            });

            window.assistant.sendMessage(cleanMessage);
            this.stopListening();
          }
        }
      };

      this.recognition.onerror = (event) => {
        console.error("JARVIS Voice Error:", event.error);
        // Handle common errors gracefully
        if (event.error === 'no-speech') {
          // No speech detected - this is normal, just stop
        } else if (event.error === 'not-allowed') {
          useAssistantStore.getState().addMessage({
            id: Date.now().toString(),
            role: 'system',
            content: "Microphone access denied. Please allow microphone in browser settings.",
            createdAt: new Date().toISOString()
          });
        }
        useAssistantStore.getState().setListening(false);
        this.isListening = false;
      };

      this.recognition.onend = () => {
        useAssistantStore.getState().setListening(false);
        this.isListening = false;
      };

      this.recognition.onstart = () => {
        console.log("JARVIS: Voice recognition started");
      };
    } else {
      console.warn("JARVIS: Voice capture unavailable on this system.");
      useAssistantStore.getState().addMessage({
        id: Date.now().toString(),
        role: 'system',
        content: "Voice recognition not supported. Please use Chrome or Edge browser.",
        createdAt: new Date().toISOString()
      });
    }
  }

  startListening() {
    if (!this.isAvailable) {
      return;
    }

    if (this.recognition && !this.isListening) {
      try {
        this.recognition.start();
        this.isListening = true;
        useAssistantStore.getState().setListening(true);
        console.log("JARVIS: Listening for voice...");
      } catch (e) {
        console.log("JARVIS: Voice recognition error:", e.message);
        // If already started, try to restart
        try {
          this.recognition.stop();
          setTimeout(() => {
            this.recognition.start();
            this.isListening = true;
          }, 100);
        } catch (e2) {
          console.log("JARVIS: Could not restart recognition");
        }
      }
    }
  }

  stopListening() {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop();
        this.isListening = false;
        useAssistantStore.getState().setListening(false);
      } catch (e) {
        console.log("JARVIS: Error stopping recognition");
      }
    }
  }

  // Check if microphone is available
  checkMicrophone() {
    return navigator.mediaDevices && navigator.mediaDevices.getUserMedia
      ? Promise.resolve(true)
      : Promise.resolve(false);
  }
}

export const micService = new MicService();
