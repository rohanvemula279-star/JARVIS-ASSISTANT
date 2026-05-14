import React, { useEffect } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { motion } from 'framer-motion';
import AssistantStatusLine from './AssistantStatusLine';
import { micService } from '../services/speech/micService';

const CenterAssistantOrb = () => {
  const { mode, setAssistantActive, assistantActive, muted, setMuted } = useAssistantStore();

  const handleClick = () => {
    const newState = !assistantActive;
    setAssistantActive(newState);
    if (!newState && window.assistant) {
      window.assistant.toggleActive();
      micService.stopListening();
    } else if (newState) {
      micService.startListening();
    }
  };

  const handleDoubleClick = (e) => {
    e.stopPropagation();
    toggleMute();
  };

  const toggleMute = () => {
    setMuted(!muted);
    if (window.assistant) {
      window.assistant.toggleMute();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    } else if (e.key === 'm') {
      e.preventDefault();
      toggleMute();
    }
  };

  let ringColor = 'border-white/20';
  let innerGlow = 'bg-white/5';
  let scale = 1;
  let pulse = false;

  switch (mode) {
    case 'listening':
      ringColor = 'border-jarvis-cyan/60';
      innerGlow = 'bg-jarvis-cyan/20';
      scale = 1.05;
      pulse = true;
      break;
    case 'thinking':
    case 'processing':
    case 'executing':
      ringColor = 'border-white/60';
      innerGlow = 'bg-white/20';
      scale = 0.95;
      pulse = true;
      break;
    case 'responding':
      ringColor = 'border-jarvis-cyan border-opacity-80';
      innerGlow = 'bg-jarvis-cyan/30';
      scale = 1.1;
      pulse = true;
      break;
    case 'muted':
      ringColor = 'border-red-500/40';
      innerGlow = 'bg-red-500/10';
      break;
    case 'error':
      ringColor = 'border-red-500/80';
      innerGlow = 'bg-red-500/30';
      break;
    case 'idle':
      ringColor = 'border-white/40';
      innerGlow = 'bg-white/10';
      break;
    default: // inactive
      ringColor = 'border-white/10';
      innerGlow = 'bg-transparent';
      break;
  }

  return (
    <div className="flex flex-col items-center justify-center space-y-8">
      <motion.div 
        role="button"
        aria-label={`JARVIS Assistant: ${assistantActive ? 'Active' : 'Inactive'}, Mode: ${mode}`}
        tabIndex={0}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        onKeyDown={handleKeyDown}
        animate={{ scale }}
        transition={{ type: 'spring', stiffness: 200, damping: 20 }}
        className="relative w-64 h-64 rounded-full flex items-center justify-center cursor-pointer group focus:outline-none focus:ring-2 focus:ring-jarvis-cyan/50 focus:ring-offset-8 focus:ring-offset-black"
      >
        {/* Outer Ring */}
        <motion.div 
          animate={pulse ? { rotate: 360 } : { rotate: 0 }}
          transition={{ repeat: Infinity, duration: 8, ease: "linear" }}
          className={`absolute inset-0 rounded-full border-2 ${ringColor} border-dashed opacity-50`}
        />
        
        {/* Inner Ring */}
        <div className={`absolute inset-4 rounded-full border border-t-transparent border-l-transparent ${ringColor} opacity-70 transition-colors duration-500`} />

        {/* Core */}
        <div className={`w-40 h-40 rounded-full ${innerGlow} backdrop-blur-md shadow-glow-white flex items-center justify-center transition-all duration-500`}>
           {/* Center Text */}
           <div className="flex items-center justify-center">
             <span className="text-white/90 font-mono tracking-[0.2em] font-bold text-xl uppercase">JARVIS</span>
           </div>
        </div>
      </motion.div>

      {/* Status Label */}
      <div className="flex flex-col items-center space-y-2">
        <div className="font-mono text-sm tracking-[0.3em] uppercase text-white/50 transition-colors duration-300">
          {muted ? 'MUTED' : mode}
        </div>
        <AssistantStatusLine />
      </div>
    </div>
  );
};

export default CenterAssistantOrb;
