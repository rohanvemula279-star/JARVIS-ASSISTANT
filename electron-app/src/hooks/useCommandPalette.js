import { useState, useEffect } from 'react';
import { useAssistantStore } from '../state/assistantStore';

export const useCommandPalette = () => {
  const { commandPaletteOpen, setCommandPaletteOpen } = useAssistantStore();
  
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      
      if (e.key === 'Escape' && commandPaletteOpen) {
        setCommandPaletteOpen(false);
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, setCommandPaletteOpen]);
  
  return { isOpen: commandPaletteOpen, open: () => setCommandPaletteOpen(true), close: () => setCommandPaletteOpen(false) };
};