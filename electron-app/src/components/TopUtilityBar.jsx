import React from 'react';
import { X, Minimize2, Square, Camera, Mic, MicOff } from 'lucide-react';
import { useAssistantStore } from '../state/assistantStore';

const TopUtilityBar = () => {
  const { cameraEnabled, micEnabled, toggleCamera, toggleMic } = useAssistantStore();

  const handleMinimize = () => {
    window.electronAPI?.windowControl?.minimize?.();
  };

  const handleMaximize = () => {
    window.electronAPI?.windowControl?.maximize?.();
  };

  const handleClose = () => {
    window.electronAPI?.windowControl?.close?.();
  };

  return (
    <div className="toputilitybar absolute top-0 right-0 flex items-center gap-2 p-2 z-50">
      {/* Microphone Toggle */}
      <button
        onClick={toggleMic}
        className={`p-1.5 rounded transition-colors ${micEnabled ? 'hover:bg-white/10' : 'bg-red-500/20 hover:bg-red-500/30'}`}
        title={micEnabled ? 'Microphone ON - Click to mute' : 'Microphone OFF - Click to enable'}
      >
        {micEnabled ? (
          <Mic size={16} className="text-green-400" />
        ) : (
          <MicOff size={16} className="text-red-400" />
        )}
      </button>

      {/* Camera Toggle */}
      <button
        onClick={toggleCamera}
        className={`p-1.5 rounded transition-colors ${cameraEnabled ? 'hover:bg-white/10' : 'bg-amber-500/20 hover:bg-amber-500/30'}`}
        title={cameraEnabled ? 'Camera ON - Click to disable' : 'Camera OFF - Click to enable'}
      >
        {cameraEnabled ? (
          <Camera size={16} className="text-jarvis-cyan" />
        ) : (
          <Camera size={16} className="text-amber-400" />
        )}
      </button>

      <div className="w-px h-4 bg-white/20 mx-1" />

      <button
        onClick={handleMinimize}
        className="p-1 hover:bg-white/10 rounded transition-colors"
        title="Minimize"
      >
        <Minimize2 size={16} className="text-white/60 hover:text-white/90" />
      </button>
      <button
        onClick={handleMaximize}
        className="p-1 hover:bg-white/10 rounded transition-colors"
        title="Maximize"
      >
        <Square size={16} className="text-white/60 hover:text-white/90" />
      </button>
      <button
        onClick={handleClose}
        className="p-1 hover:bg-red-500/20 rounded transition-colors"
        title="Close"
      >
        <X size={16} className="text-white/60 hover:text-red-500" />
      </button>
    </div>
  );
};

export default TopUtilityBar;
