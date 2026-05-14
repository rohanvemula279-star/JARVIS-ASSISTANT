import React, { useEffect, useRef } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { Brain, Search, FileText, Terminal, CheckCircle, XCircle, Users } from 'lucide-react';

const PROFILE_COLORS = {
  RESEARCHER: 'bg-teal-500',
  EXECUTOR: 'bg-blue-500',
  ANALYST: 'bg-purple-500',
  CODER: 'bg-amber-500',
  DEFAULT: 'bg-gray-500',
};

const PROFILE_BORDER = {
  RESEARCHER: 'border-teal-500/50',
  EXECUTOR: 'border-blue-500/50',
  ANALYST: 'border-purple-500/50',
  CODER: 'border-amber-500/50',
  DEFAULT: 'border-gray-500/50',
};

const AgentStepsPanel = () => {
  const { mode, activeSteps, activeAgents } = useAssistantStore();
  const scrollRef = useRef(null);
  const fadeTimeoutRef = useRef(null);
  const [isFading, setIsFading] = React.useState(false);

  useEffect(() => {
    if (scrollRef.current && activeSteps.length > 0) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activeSteps]);

  useEffect(() => {
    if (mode === 'idle' && activeSteps.length > 0) {
      fadeTimeoutRef.current = setTimeout(() => {
        setIsFading(true);
        setTimeout(() => setIsFading(false), 3000);
      }, 2000);
    }
    return () => {
      if (fadeTimeoutRef.current) {
        clearTimeout(fadeTimeoutRef.current);
      }
    };
  }, [mode, activeSteps]);

  const hasAgentActivity = activeAgents.length > 0;

  if (activeSteps.length === 0 && !hasAgentActivity && (mode === 'idle' && !isFading)) {
    return null;
  }

  const getStepIcon = (type) => {
    switch (type) {
      case 'thought': return <Brain size={12} className="text-jarvis-cyan" />;
      case 'action': return <Terminal size={12} className="text-orange-400" />;
      case 'observation': return <Search size={12} className="text-green-400" />;
      case 'answer': return <CheckCircle size={12} className="text-jarvis-cyan" />;
      case 'agent_spawned': return <Users size={12} className="text-blue-400" />;
      case 'agent_complete': return <CheckCircle size={12} className="text-green-400" />;
      case 'agent_failed': return <XCircle size={12} className="text-red-400" />;
      case 'skill_learned': return <Brain size={12} className="text-amber-400" />;
      default: return <FileText size={12} className="text-white/50" />;
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case 'thought': return 'Thinking';
      case 'action': return 'Action';
      case 'observation': return 'Result';
      case 'answer': return 'Answer';
      case 'agent_spawned': return 'Agent Spawned';
      case 'agent_complete': return 'Agent Complete';
      case 'agent_failed': return 'Agent Failed';
      case 'skill_learned': return 'Skill Learned';
      default: return type;
    }
  };

  return (
    <div
      className={`
        absolute bottom-20 left-4 w-72 max-h-96 bg-jarvis-black/95 backdrop-blur-xl
        border border-white/10 rounded-lg overflow-hidden
        transition-all duration-500 ease-in-out
        ${isFading ? 'opacity-0 translate-y-2' : 'opacity-100 translate-y-0'}
        ${hasAgentActivity ? 'border-blue-500/50' : mode === 'thinking' ? 'border-orange-500/50' : 'border-white/10'}
      `}
    >
      <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between bg-white/5">
        <div className="flex items-center gap-2">
          {hasAgentActivity ? (
            <Users size={14} className="text-blue-400 animate-pulse" />
          ) : (
            <Brain size={14} className="text-jarvis-cyan animate-pulse" />
          )}
          <span className="text-[10px] uppercase tracking-wider text-white/70">
            {hasAgentActivity ? 'Agent Coordination' : 'Agent Steps'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[9px] text-white/40 uppercase">
            {hasAgentActivity ? 'Multi-Agent' : mode === 'thinking' ? 'Processing...' : 'Responding'}
          </span>
          <div className={`w-1.5 h-1.5 rounded-full ${
            hasAgentActivity ? 'bg-blue-500 animate-pulse' : mode === 'thinking' ? 'bg-orange-500 animate-pulse' : 'bg-jarvis-cyan animate-pulse'
          }`} />
        </div>
      </div>

      {/* Active Agents Row */}
      {activeAgents.length > 0 && (
        <div className="px-3 py-2 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-2">
            {activeAgents.map((agent) => (
              <div
                key={agent.id}
                className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[9px] border ${
                  PROFILE_BORDER[agent.profile] || 'border-gray-500/50'
                } bg-white/5`}
                title={agent.task}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${
                  PROFILE_COLORS[agent.profile] || 'bg-gray-500'
                } ${agent.status === 'running' ? 'animate-pulse' : ''}`} />
                <span className="text-white/70 uppercase tracking-wider">
                  {agent.profile}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Steps List */}
      <div
        ref={scrollRef}
        className="p-2 space-y-2 max-h-48 overflow-y-auto scrollbar-thin"
      >
        {activeSteps.map((step, index) => (
          <div
            key={index}
            className="flex items-start gap-2 text-[10px] p-2 rounded bg-white/5"
          >
            <div className="flex-shrink-0 mt-0.5">
              {getStepIcon(step.type)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-white/50 uppercase text-[9px]">
                  {getTypeLabel(step.type)}
                </span>
                {step.iteration != null && (
                  <span className="text-white/30 text-[8px]">
                    #{step.iteration}
                  </span>
                )}
              </div>
              <div className="text-white/80 truncate">
                {step.tool && !['agent_spawned', 'agent_complete', 'agent_failed'].includes(step.type) && (
                  <span className="text-orange-300">
                    🔧 {step.tool}:
                  </span>
                )}
                {' '}
                {step.content && step.content.slice(0, 100)}
                {(step.content || '').length > 100 && '...'}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="px-3 py-1.5 border-t border-white/10 bg-white/5 flex justify-between">
        <span className="text-[9px] text-white/30">
          {activeSteps.length} step{activeSteps.length !== 1 ? 's' : ''}
        </span>
        {activeAgents.length > 0 && (
          <span className="text-[9px] text-blue-400/60">
            {activeAgents.length} active agent{activeAgents.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  );
};

export default AgentStepsPanel;
