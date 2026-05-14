import React, { useState, useEffect } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { useBackendStream } from '../hooks/useAssistantState';
import ReactMarkdown from 'react-markdown';
import { Send, Terminal } from 'lucide-react';

const ChatPanel = () => {
  const { messages, mode, providerStatus, connectionHealth } = useAssistantStore();
  const [input, setInput] = useState('');
  const { sendMessage } = useBackendStream();

  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return 'bg-jarvis-cyan';
      case 'offline': return 'bg-red-500';
      case 'missing_key': return 'bg-orange-500';
      case 'error': return 'bg-red-500 animate-pulse';
      default: return 'bg-white/10';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const textToSend = input;
    setInput('');

    // Send to backend for streaming response
    await sendMessage(textToSend);
  };

  return (
    <div className="flex flex-col h-full bg-jarvis-black/90 backdrop-blur-xl border-l border-white/10 font-mono text-sm shadow-2xl">
      {/* Header */}
      <div className="h-20 border-b border-white/10 flex flex-col shrink-0">
        <div className="flex-1 flex items-center px-6 justify-between">
          <div className="flex items-center gap-2 text-white/80 uppercase tracking-widest text-xs">
            <Terminal size={14} />
            <span>Neural Link</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-[8px] text-white/30 uppercase tracking-tighter">NIM</span>
              <div className={`w-1.5 h-1.5 rounded-full ${getStatusColor(providerStatus.nim)}`} />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[8px] text-white/30 uppercase tracking-tighter">GEM</span>
              <div className={`w-1.5 h-1.5 rounded-full ${getStatusColor(providerStatus.gemini)}`} />
            </div>
          </div>
        </div>
        <div className="px-6 pb-2 flex items-center justify-between">
           <div className="flex items-center gap-2">
             <div className={`w-2 h-2 rounded-full ${mode === 'responding' || mode === 'processing' || mode === 'thinking' ? 'bg-jarvis-cyan animate-pulse' : 'bg-white/20'}`} />
             <span className="text-[10px] text-white/40 uppercase tracking-widest">{mode}</span>
           </div>
           <span className={`text-[8px] px-1.5 py-0.5 border border-white/10 rounded uppercase tracking-widest ${connectionHealth === 'good' ? 'text-jarvis-cyan' : 'text-orange-500'}`}>
             Health: {connectionHealth}
           </span>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide">
        {messages.length === 0 && (
          <div className="text-center text-white/30 py-12">
            <p className="uppercase tracking-widest text-xs">Awaiting transmission...</p>
            <p className="text-[10px] mt-2 opacity-50">Start a conversation with JARVIS</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className="flex items-center gap-2 mb-1 opacity-40 text-[10px] uppercase tracking-wider">
               <span>{msg.role}</span>
               <span>•</span>
               <span>{new Date(msg.createdAt).toLocaleTimeString()}</span>
            </div>
            <div className={`max-w-[85%] p-3 ${msg.role === 'user' ? 'bg-white/10 border border-white/20 text-white rounded-tl-lg rounded-tr-lg rounded-bl-lg' : 'bg-transparent text-white/90 border-l border-white/30 pl-4'}`}>
               {msg.role === 'assistant' ? (
                 <div className="prose prose-invert prose-sm">
                   {msg.streaming && msg.content === '' ? (
                     <span className="text-white/50 animate-pulse">Processing...</span>
                   ) : (
                     <ReactMarkdown>{msg.content || (msg.streaming ? '▊' : '')}</ReactMarkdown>
                   )}
                 </div>
               ) : (
                 <p>{msg.content}</p>
               )}
            </div>
            {msg.error && (
              <div className="text-red-400 text-[10px] mt-1 px-2">
                Error: {msg.error}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Composer */}
      <div className="p-4 border-t border-white/10 bg-jarvis-dark">
        <form onSubmit={handleSubmit} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="TYPE COMMAND..."
            disabled={mode === 'thinking' || mode === 'processing'}
            className="w-full bg-black/50 border border-white/20 rounded-md px-4 py-3 text-white/90 placeholder:text-white/30 focus:outline-none focus:border-jarvis-cyan/50 focus:ring-1 focus:ring-jarvis-cyan/50 transition-all font-mono text-xs uppercase disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={mode === 'thinking' || mode === 'processing' || !input.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-white/50 hover:text-white transition-colors disabled:opacity-30"
          >
            <Send size={14} />
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatPanel;