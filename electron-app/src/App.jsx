import React, { useEffect } from 'react';
import CenterAssistantOrb from './components/CenterAssistantOrb';
import ChatPanel from './components/ChatPanel';
import CameraWidget from './components/CameraWidget';
import DateTimeWidget from './components/DateTimeWidget';
import LiveContextPanel from './components/LiveContextPanel';
import CommandPalette from './components/CommandPalette';
import SkillLibrary from './components/SkillLibrary';
import TopUtilityBar from './components/TopUtilityBar';
import { useAssistantState } from './hooks/useAssistantState';
import { useAssistantStore } from './state/assistantStore';
import { micService } from './services/speech/micService';

const App = () => {
  const { mode } = useAssistantStore();
  useAssistantState(); // Bind IPC events to store

  useEffect(() => {
    const handleKeyDown = (e) => {
      // If we're in an input, don't trigger global shortcuts
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      if (e.code === 'Space' && e.ctrlKey) {
        e.preventDefault();
        micService.startListening();
      } else if (e.code === 'Space') {
        // Toggle active state on Space if not focused elsewhere
        e.preventDefault();
        const { assistantActive } = useAssistantStore.getState();
        useAssistantStore.getState().setAssistantActive(!assistantActive);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Dynamic gradient based on mode
  const getGradient = () => {
    switch(mode) {
      case 'listening':
        return 'from-cyan-900/30 via-black to-blue-900/30';
      case 'thinking':
        return 'from-purple-900/30 via-black to-pink-900/30';
      case 'responding':
        return 'from-green-900/30 via-black to-teal-900/30';
      default:
        return 'from-jarvis-gray/20 via-black to-black';
    }
  };

  return (
    <div className="h-screen w-screen bg-black overflow-hidden flex relative selection:bg-white/20 font-mono text-white">

      {/* Beautiful Animated Gradient Background */}
      <div className={`absolute inset-0 bg-gradient-to-br ${getGradient()} z-0 pointer-events-none transition-all duration-1000`} />

      {/* Animated Aurora Borealis Effect */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-20">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      {/* Grid Overlay for texture */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-[0.03]"
           style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      {/* Main Dashboard Area (Left/Center) */}
      <div className="flex-1 relative z-10 flex flex-col pointer-events-none">
        
        {/* Top Left: Camera */}
        <div className="absolute top-6 left-6 z-20 pointer-events-auto">
          <CameraWidget />
        </div>

        {/* Center: Main Assistant Orb */}
        <div className="flex-1 flex items-center justify-center relative pointer-events-auto">
          <CenterAssistantOrb />
        </div>

        {/* Bottom Left: Live Context */}
        <div className="absolute bottom-6 left-6 z-20 pointer-events-auto">
          <LiveContextPanel />
        </div>
      </div>

      {/* Right Side: Chat Panel */}
      <div className="w-[450px] h-full relative z-20 flex-shrink-0 pointer-events-auto shadow-[-20px_0_50px_rgba(0,0,0,0.5)]">
        <ChatPanel />
      </div>
      
      {/* Date Time Widget (Anchored to main screen bottom right, before chat) */}
      <div className="absolute bottom-6 right-[480px] z-20 pointer-events-none">
         <DateTimeWidget />
      </div>

      {/* Global Overlays */}
      <CommandPalette />
      <SkillLibrary />

      {/* Top Utility Bar with Window Controls */}
      <div className="absolute top-0 right-0 z-50 pointer-events-auto">
        <TopUtilityBar />
      </div>
      
      {/* Top Utility Hint */}
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-0 pointer-events-none opacity-30 text-[10px] uppercase tracking-widest text-white">
        Hold <kbd className="bg-white/10 px-1 py-0.5 rounded border border-white/20 mx-1 shadow-glow-white">CTRL</kbd> + <kbd className="bg-white/10 px-1 py-0.5 rounded border border-white/20 shadow-glow-white">SPACE</kbd> for Voice
      </div>

    </div>
  );
};

export default App;
