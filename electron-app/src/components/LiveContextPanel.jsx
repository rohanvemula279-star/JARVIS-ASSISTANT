import React, { useEffect, useState } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { CloudRain, MapPin, Calendar, Activity, Rss } from 'lucide-react';

const LiveContextPanel = () => {
  const { liveContextData, providerStatus } = useAssistantStore();
  const [data, setData] = useState(liveContextData);
  const [loading, setLoading] = useState(!liveContextData);

  useEffect(() => {
    if (liveContextData) {
      setData(liveContextData);
      setLoading(false);
    }
  }, [liveContextData]);

  useEffect(() => {
    if (!liveContextData && window.assistant) {
       setLoading(true);
       window.assistant.getLiveContext().then(res => {
         if (res) setData(res);
         setLoading(false);
       });
    }
  }, []);

  const Skeleton = () => (
    <div className="bg-jarvis-black/40 border border-white/5 p-3 rounded backdrop-blur-md w-64 h-16 animate-pulse flex flex-col justify-center gap-2">
      <div className="h-2 w-24 bg-white/10 rounded" />
      <div className="h-3 w-40 bg-white/5 rounded" />
    </div>
  );

  return (
    <div className="flex flex-col gap-3 font-mono">
      <div className="text-[10px] text-jarvis-cyan uppercase tracking-[0.2em] mb-1 flex items-center gap-2">
        <Activity size={12} className={`\${loading ? 'animate-spin' : 'animate-pulse'}`} />
        <span>Live Telemetry</span>
      </div>

      {loading ? (
        <>
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </>
      ) : (
        <>
          {/* Card 1: Location & Weather */}
          <div className="bg-jarvis-black/80 border border-white/10 p-3 rounded backdrop-blur-md w-64 shadow-xl transition-all hover:border-white/20">
            <div className="flex items-start justify-between text-xs text-white/80 mb-2">
              <div className="flex items-center gap-2">
                <MapPin size={12} className="text-white/40"/> 
                <span className="uppercase tracking-widest">{data?.location || 'Sector Unknown'}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm text-white">
              <CloudRain size={14} className="text-jarvis-cyan"/>
              <span className="uppercase">{data?.weather || 'Analyzing Atmosphere...'}</span>
            </div>
          </div>

          {/* Card 2: Global Feed */}
          <div className="bg-jarvis-black/80 border border-white/10 p-3 rounded backdrop-blur-md w-64 shadow-xl transition-all hover:border-white/20">
            <div className="flex items-center gap-2 text-xs text-white/50 mb-2 uppercase tracking-widest">
              <Rss size={12} /> <span>Global Feed</span>
            </div>
            <div className={`text-xs leading-relaxed uppercase \${providerStatus.gemini === 'offline' ? 'text-red-400' : 'text-white/90'}`}>
              {data?.headline || 'JARVIS: Awaiting transmission stream...'}
            </div>
          </div>

          {/* Card 3: System Status */}
          <div className="bg-jarvis-black/80 border border-white/10 p-3 rounded backdrop-blur-md w-64 shadow-xl transition-all hover:border-white/20">
            <div className="flex flex-col gap-1 text-xs uppercase tracking-widest">
               <div className="flex justify-between">
                 <span className="text-white/40">Core</span>
                 <span className={`\${providerStatus.nim === 'online' ? 'text-jarvis-cyan' : 'text-orange-500'}`}>
                   {providerStatus.nim === 'online' ? 'Nominal' : 'Limited'}
                 </span>
               </div>
               <div className="flex justify-between">
                 <span className="text-white/40">Network</span>
                 <span className="text-white/80">{data?.system || 'Uplink Established'}</span>
               </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default LiveContextPanel;
