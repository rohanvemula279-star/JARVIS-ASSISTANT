import React, { useState, useEffect, useCallback } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { Brain, Trash2, Play, X, Star, Clock, TrendingUp } from 'lucide-react';

const BACKEND_URL = 'http://127.0.0.1:8000';

const SkillLibrary = () => {
  const { commandPaletteOpen } = useAssistantStore();
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [testInput, setTestInput] = useState('');

  useEffect(() => {
    if (!open) return;
    loadSkills();
  }, [open]);

  const loadSkills = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/skills`);
      const data = await res.json();
      setSkills(data.skills || []);
    } catch (e) {
      console.error('Failed to load skills:', e);
    }
    setLoading(false);
  };

  const handleForget = async (name) => {
    try {
      await fetch(`${BACKEND_URL}/api/v1/skills/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      });
      setSkills((prev) => prev.filter((s) => s.name !== name));
    } catch (e) {
      console.error('Failed to delete skill:', e);
    }
  };

  const handleTest = async (name) => {
    if (!testInput) return;
    const skill = skills.find((s) => s.name === name);
    if (!skill) return;

    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/skills/${encodeURIComponent(name)}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: testInput }),
      });

      if (!res.ok) {
        console.error('Test skill failed:', res.status);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventType = 'message';
      let output = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && eventType === 'token') {
            const data = JSON.parse(line.slice(6));
            if (data.text) output += data.text;
          }
        }
      }

      alert(`Test completed.\n\nOutput:\n${output.slice(0, 500)}`);
    } catch (e) {
      console.error('Test skill error:', e);
    }
  };

  useEffect(() => {
    const down = (e) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey) && e.shiftKey) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  if (!open) return null;

  const getSuccessRateColor = (rate) => {
    if (rate >= 0.8) return 'bg-green-500';
    if (rate >= 0.6) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[5vh] pb-[5vh] bg-black/60 backdrop-blur-sm transition-opacity">
      <div className="w-full max-w-3xl bg-jarvis-charcoal border border-white/10 rounded-lg shadow-2xl overflow-hidden font-mono flex flex-col h-full max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-jarvis-dark shrink-0">
          <div className="flex items-center gap-3">
            <Brain size={16} className="text-amber-400" />
            <span className="text-white/80 uppercase tracking-widest text-sm">Skill Library</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded border border-white/10 text-white/40">
              Shift+Ctrl+K
            </span>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1 text-white/40 hover:text-white/80 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && (
            <div className="text-center text-white/40 py-12">
              <Brain size={24} className="mx-auto mb-3 animate-pulse text-amber-400/50" />
              <span className="text-xs uppercase tracking-wider">Loading skills...</span>
            </div>
          )}

          {!loading && skills.length === 0 && (
            <div className="text-center text-white/40 py-12">
              <Brain size={24} className="mx-auto mb-3 text-white/20" />
              <span className="text-xs uppercase tracking-wider">No skills learned yet</span>
              <p className="text-[10px] mt-2 text-white/30">
                Skills are automatically extracted from successful multi-step tasks
              </p>
            </div>
          )}

          {!loading && skills.map((skill) => (
            <div
              key={skill.name}
              className="border border-white/10 rounded-lg p-4 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Star size={12} className="text-amber-400" />
                    <span className="text-sm text-white/90 uppercase tracking-wider">
                      {skill.name.replace(/-/g, ' ')}
                    </span>
                  </div>
                  <p className="text-[10px] text-white/50 mt-1">
                    {skill.description}
                  </p>
                </div>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <button
                    onClick={() => handleForget(skill.name)}
                    className="p-1.5 text-red-400/50 hover:text-red-400 hover:bg-red-500/10 rounded transition-all"
                    title="Forget this skill"
                  >
                    <Trash2 size={14} />
                  </button>
                  <button
                    onClick={() => {
                      setTestInput(skill.trigger_phrases?.[0] || '');
                      const input = prompt('Enter test input:', skill.trigger_phrases?.[0] || '');
                      if (input) {
                        setTestInput(input);
                        handleTest(skill.name);
                      }
                    }}
                    className="p-1.5 text-jarvis-cyan/50 hover:text-jarvis-cyan hover:bg-jarvis-cyan/10 rounded transition-all"
                    title="Run this skill"
                  >
                    <Play size={14} />
                  </button>
                </div>
              </div>

              {/* Stats Row */}
              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/5">
                <div className="flex items-center gap-1.5">
                  <TrendingUp size={10} className="text-white/30" />
                  <span className="text-[9px] text-white/40 uppercase">Rate</span>
                  <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${getSuccessRateColor(skill.success_rate)}`}
                      style={{ width: `${skill.success_rate * 100}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-white/60">{Math.round(skill.success_rate * 100)}%</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Play size={10} className="text-white/30" />
                  <span className="text-[9px] text-white/40 uppercase">Used</span>
                  <span className="text-[9px] text-white/60">{skill.times_used}x</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Clock size={10} className="text-white/30" />
                  <span className="text-[9px] text-white/40 uppercase">Avg</span>
                  <span className="text-[9px] text-white/60">{Math.round(skill.avg_duration_s)}s</span>
                </div>
                {skill.trigger_phrases?.length > 0 && (
                  <div className="flex-1 text-right">
                    <span className="text-[8px] text-white/30">
                      Triggers: {skill.trigger_phrases.slice(0, 2).join(', ')}
                      {skill.trigger_phrases.length > 2 && '...'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-white/10 bg-white/5 flex justify-between items-center">
          <span className="text-[9px] text-white/30">
            {skills.length} skill{skills.length !== 1 ? 's' : ''} available
          </span>
          <button
            onClick={loadSkills}
            className="text-[9px] text-white/40 hover:text-white/70 uppercase tracking-wider transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
};

export default SkillLibrary;
