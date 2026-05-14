import React, { useEffect, useState } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { Command } from 'cmdk';
import { Search, Mic, VolumeX, Camera, Power, RefreshCw, Terminal, Brain } from 'lucide-react';

const CommandPalette = () => {
  const { commandPaletteOpen, setCommandPaletteOpen, assistantActive, muted, tasks } = useAssistantStore();

  useEffect(() => {
    const down = (e) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  if (!commandPaletteOpen) return null;

  // Group tasks by origin
  const groupedTasks = tasks.reduce((acc, task) => {
    const origin = task.origin || 'Local';
    if (!acc[origin]) acc[origin] = [];
    acc[origin].push(task);
    return acc;
  }, {});

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] pb-[10vh] bg-black/60 backdrop-blur-sm transition-opacity">
      <div className="w-full max-w-2xl bg-jarvis-charcoal border border-white/10 rounded-lg shadow-2xl overflow-hidden font-mono flex flex-col h-full max-h-[80vh]">
        <Command label="Command Palette" className="flex flex-col w-full h-full overflow-hidden">
          <div className="flex items-center px-4 py-3 border-b border-white/10 bg-jarvis-dark shrink-0">
            <Search size={16} className="text-white/40 mr-3" />
            <Command.Input 
              placeholder="SEARCH PROTOCOLS & AGENTS..." 
              className="flex-1 bg-transparent border-none text-white/90 text-sm focus:outline-none placeholder:text-white/30 uppercase tracking-widest"
              autoFocus
            />
            <div className="text-[10px] text-white/30 border border-white/20 rounded px-1.5 py-0.5 ml-2">ESC</div>
          </div>
          <Command.List className="overflow-y-auto p-2 scrollbar-hide flex-1">
            <Command.Empty className="py-6 text-center text-sm text-white/40 uppercase tracking-widest">No matching protocols found.</Command.Empty>
            
            <Command.Group heading="SYSTEM CONTROLS" className="text-xs text-white/40 uppercase tracking-widest px-2 py-2">
              <Command.Item 
                onSelect={() => { window.assistant?.toggleActive(); setCommandPaletteOpen(false); }}
                className="flex items-center px-3 py-2 mt-1 text-sm text-white/80 bg-transparent rounded cursor-pointer hover:bg-white/10 aria-selected:bg-white/10 transition-colors"
              >
                <Power size={14} className="mr-3 text-jarvis-cyan" />
                <span>{assistantActive ? 'DEACTIVATE ASSISTANT' : 'ACTIVATE ASSISTANT'}</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => { 
                  setCommandPaletteOpen(false);
                  // Dispatch keyboard event to open SkillLibrary (Shift+Ctrl+K)
                  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, shiftKey: true }));
                }}
                className="flex items-center px-3 py-2 mt-1 text-sm text-white/80 bg-transparent rounded cursor-pointer hover:bg-white/10 aria-selected:bg-white/10 transition-colors"
              >
                <Brain size={14} className="mr-3 text-amber-400" />
                <span>SKILL LIBRARY</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => { window.assistant?.toggleMute(); setCommandPaletteOpen(false); }}
                className="flex items-center px-3 py-2 mt-1 text-sm text-white/80 bg-transparent rounded cursor-pointer hover:bg-white/10 aria-selected:bg-white/10 transition-colors"
              >
                <VolumeX size={14} className="mr-3 text-white/60" />
                <span>{muted ? 'UNMUTE AUDIO' : 'MUTE AUDIO'}</span>
              </Command.Item>
            </Command.Group>
            
            {Object.entries(groupedTasks).map(([origin, originTasks]) => (
              <Command.Group key={origin} heading={`${origin.toUpperCase()} MODULES`} className="text-[10px] text-jarvis-cyan/60 uppercase tracking-widest px-2 py-2 mt-2 border-t border-white/5">
                {originTasks.map(task => (
                  <Command.Item 
                    key={task.id}
                    onSelect={() => { window.assistant?.executeCommand({ name: task.name }); setCommandPaletteOpen(false); }}
                    className="flex flex-col items-start px-3 py-2 mt-1 text-sm text-white/80 bg-transparent rounded cursor-pointer hover:bg-white/10 aria-selected:bg-white/10 transition-colors group"
                  >
                    <div className="flex items-center w-full">
                      <Terminal size={12} className="mr-3 text-white/40 group-hover:text-white/80 transition-colors" />
                      <span className="uppercase tracking-wider">{task.name.replace(/_/g, ' ')}</span>
                      <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded border border-white/10 text-white/30 uppercase group-hover:text-white/50 group-hover:border-white/20 transition-all">
                        {task.kind}
                      </span>
                    </div>
                    <div className="text-[10px] text-white/40 mt-1 pl-6 lowercase tracking-normal max-w-[90%] truncate">
                      {task.description}
                    </div>
                  </Command.Item>
                ))}
              </Command.Group>
            ))}

          </Command.List>
        </Command>
      </div>
    </div>
  );
};

export default CommandPalette;
